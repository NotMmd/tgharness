import asyncio
import time
import uuid
from typing import Any

from .accounts import AccountPool, account_identity
from .gateway import dispatch, envelope, error_envelope


def _select_accounts(
    pool: AccountPool,
    account_names: list[str] | None = None,
    *,
    all_accounts: bool = False,
) -> list[str]:
    if all_accounts:
        names = pool.config.account_names(enabled_only=True)
        if not names:
            raise RuntimeError("No enabled tgharness accounts are configured")
        return names
    if account_names:
        # Preserve user order while removing duplicates.
        names = list(dict.fromkeys(account_names))
        for name in names:
            pool.config.account(name)  # validate existence + enabled
        return names
    return [pool.config.account().name]


def _batch_envelope(
    children: list[dict[str, Any]],
    accounts: list[str],
    command: str,
    *,
    request_id: str,
    started: float,
) -> dict[str, Any]:
    results = [
        {
            "account": account,
            "ok": child.get("ok", False),
            "data": child.get("data"),
            "error": child.get("error"),
            "meta": child.get("meta", {}),
        }
        for account, child in zip(accounts, children)
    ]
    failures = sum(1 for child in children if not child.get("ok"))
    return {
        "ok": failures == 0,
        "data": {"results": results},
        "error": None
        if failures == 0
        else {
            "type": "BatchOperationError",
            "message": f"{failures} of {len(accounts)} account operations failed",
        },
        "meta": {
            "request_id": request_id,
            "operation": command,
            "accounts": accounts,
            "success_count": len(accounts) - failures,
            "failure_count": failures,
            "duration_ms": round((time.monotonic() - started) * 1000, 3),
        },
    }


async def _dispatch_one(
    pool: AccountPool,
    account: str,
    command: str,
    args: dict[str, Any],
    *,
    request_id: str,
) -> dict[str, Any]:
    try:
        app = await pool.get(account)
    except Exception as exc:
        result = error_envelope(exc, request_id=request_id, operation=command)
        result.setdefault("meta", {})["account"] = account
        return result
    result = await dispatch(app, command, args, request_id=request_id)
    result.setdefault("meta", {})["account"] = account
    return result


async def _dispatch_batch(
    pool: AccountPool,
    accounts: list[str],
    command: str,
    args: dict[str, Any],
    *,
    request_id: str,
) -> dict[str, Any]:
    started = time.monotonic()
    children = await asyncio.gather(
        *(
            _dispatch_one(
                pool,
                name,
                command,
                args,
                request_id=f"{request_id}:{name}",
            )
            for name in accounts
        )
    )
    return _batch_envelope(children, accounts, command, request_id=request_id, started=started)


async def _inspect_account_one(
    pool: AccountPool,
    name: str,
    command: str,
    args: dict[str, Any],
    *,
    request_id: str,
) -> dict[str, Any]:
    try:
        account_cfg = pool.config.account(name)
        app = await pool.get(name)
        if command == "account_info":
            data = await account_identity(
                app,
                account_cfg,
                include_photos=args.get("photo_limit", 0) > 0 or args.get("download_photos", False),
                photo_limit=max(0, int(args.get("photo_limit", 0))),
                download_photos=args.get("download_photos", False),
                download_root=pool.config.download_dir / "profiles" / name,
            )
        else:
            limit = max(1, int(args.get("limit", 5)))
            data = await account_identity(
                app,
                account_cfg,
                include_photos=True,
                photo_limit=limit,
                download_photos=args.get("download", False),
                download_root=pool.config.download_dir / "profiles" / name,
            )
            data = {
                "account": data["account"],
                "identity": data["identity"],
                "profile_photo_count": data["profile_photo_count"],
                "profile_photos": data.get("profile_photos", []),
                "profile_photos_returned": data.get("profile_photos_returned", 0),
                "profile_photos_downloaded": data.get("profile_photos_downloaded", False),
            }
        data["account"]["default"] = name == pool.config.default_account
        return envelope(data, request_id=request_id, meta={"operation": command, "account": name})
    except Exception as exc:
        result = error_envelope(exc, request_id=request_id, operation=command)
        result.setdefault("meta", {})["account"] = name
        return result


async def _inspect_accounts(
    pool: AccountPool,
    command: str,
    args: dict[str, Any],
    *,
    request_id: str,
    account_names: list[str] | None,
    all_accounts: bool,
) -> dict[str, Any]:
    explicit_name = args.get("name")
    if explicit_name and (account_names or all_accounts):
        raise ValueError("Use either an account name or --account/--accounts/--all-accounts, not both")
    if explicit_name:
        selected = [pool.config.account(explicit_name).name]
    else:
        selected = _select_accounts(pool, account_names, all_accounts=all_accounts)

    if len(selected) == 1:
        return await _inspect_account_one(pool, selected[0], command, args, request_id=request_id)

    started = time.monotonic()
    children = await asyncio.gather(
        *(
            _inspect_account_one(
                pool,
                name,
                command,
                args,
                request_id=f"{request_id}:{name}",
            )
            for name in selected
        )
    )
    return _batch_envelope(children, selected, command, request_id=request_id, started=started)


async def dispatch_request(
    pool: AccountPool,
    command: str,
    args: dict | None = None,
    *,
    request_id: str | None = None,
    account_names: list[str] | None = None,
    all_accounts: bool = False,
) -> dict[str, Any]:
    """Route one harness request to one or more configured account sessions."""
    args = args or {}
    rid = request_id or str(uuid.uuid4())

    try:
        if command == "account_list":
            return envelope(
                pool.status(),
                request_id=rid,
                meta={"operation": command, "count": len(pool.config.account_names())},
            )

        if command == "account_add":
            account_cfg = pool.config.add_account(
                args["name"],
                session_name=args.get("session_name"),
                enabled=args.get("enabled", True),
                make_default=args.get("make_default", False),
            )
            return envelope(
                account_cfg.public_dict(default=account_cfg.name == pool.config.default_account),
                request_id=rid,
                meta={"operation": command},
            )

        if command == "account_enable":
            data = await pool.enable(args["name"])
            return envelope(data, request_id=rid, meta={"operation": command})

        if command == "account_disable":
            data = await pool.disable(args["name"])
            return envelope(data, request_id=rid, meta={"operation": command})

        if command == "account_default":
            account_cfg = pool.config.set_default_account(args["name"])
            return envelope(
                account_cfg.public_dict(default=True),
                request_id=rid,
                meta={"operation": command},
            )

        if command == "account_remove":
            data = await pool.remove(args["name"], delete_session=args.get("delete_session", False))
            return envelope(data, request_id=rid, meta={"operation": command})

        if command in {"account_info", "account_photos"}:
            return await _inspect_accounts(
                pool,
                command,
                args,
                request_id=rid,
                account_names=account_names,
                all_accounts=all_accounts,
            )

        selected = _select_accounts(pool, account_names, all_accounts=all_accounts)
        if len(selected) == 1:
            return await _dispatch_one(pool, selected[0], command, args, request_id=rid)
        return await _dispatch_batch(pool, selected, command, args, request_id=rid)
    except Exception as exc:
        return error_envelope(exc, request_id=rid, operation=command)
