import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

from . import __version__
from .core.accounts import AccountPool
from .core.auth import login_interactive, setup_interactive
from .core.config import Config, config
from .core.ipc import HarnessIPCServer, send_ipc_command
from .core.router import dispatch_request
from .core.serialization import dumps


def _json_object(value: str | None) -> dict:
    if not value:
        return {}
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return parsed


def _chat_id(value: str) -> int | str:
    stripped = value.strip()
    if stripped.lstrip("-").isdigit():
        return int(stripped)
    return stripped


def _message_ids(value: str) -> int | list[int]:
    stripped = value.strip()
    if stripped.startswith("["):
        parsed = json.loads(stripped)
        if not isinstance(parsed, list) or not all(isinstance(item, int) for item in parsed):
            raise argparse.ArgumentTypeError("message IDs JSON must be an array of integers")
        return parsed
    if "," in stripped:
        return [int(item.strip()) for item in stripped.split(",") if item.strip()]
    return int(stripped)


def _account_list(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("expected one or more comma-separated account names")
    return list(dict.fromkeys(items))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tgharness",
        description="Structured multi-account Telegram Agent Harness powered by PyroTGFork.",
    )
    parser.add_argument("--direct", action="store_true", help="bypass the IPC server and open selected session(s) directly")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument("--request-id", help="request ID to echo in the response envelope")
    parser.add_argument("--version", action="version", version=f"tgharness {__version__}")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--account", help="run the command as one configured tgharness account")
    target.add_argument("--accounts", type=_account_list, help="run as comma-separated configured accounts")
    target.add_argument("--all-accounts", action="store_true", help="run as every enabled configured account")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="configure Telegram API credentials and optionally log in the default account")
    setup.add_argument("--api-id", type=int)
    setup.add_argument("--api-hash", help="prefer the interactive prompt or TGHARNESS_API_HASH to avoid shell history")
    setup.add_argument("--session", dest="session_name")
    setup.add_argument("--workdir")
    setup.add_argument("--no-login", action="store_true")
    setup.add_argument("--phone")

    login = sub.add_parser("login", help="log in to a configured Telegram account (legacy shortcut)")
    login.add_argument("--phone")
    login.add_argument("--account", dest="login_account", help="account name; defaults to the configured default")

    sub.add_parser("serve", help="hold all enabled account sessions and serve commands over one Unix socket")

    account = sub.add_parser("account", aliases=["accounts"], help="add, inspect, enable, disable, and manage account sessions")
    account_sub = account.add_subparsers(dest="account_command", required=True)
    account_sub.add_parser("list", help="list configured accounts and session/runtime state")

    account_add = account_sub.add_parser("add", help="register another Telegram account/session")
    account_add.add_argument("name")
    account_add.add_argument("--session", dest="session_name", help="PyroTGFork session file name; defaults to account name")
    account_add.add_argument("--disabled", action="store_true", help="register it disabled")
    account_add.add_argument("--default", dest="make_default", action="store_true", help="make it the default account")
    account_add.add_argument("--login", action="store_true", help="open the interactive Telegram login flow immediately")
    account_add.add_argument("--phone")

    account_login = account_sub.add_parser("login", help="authorize one registered account interactively")
    account_login.add_argument("name", nargs="?", help="defaults to the configured default account")
    account_login.add_argument("--phone")

    for action in ("enable", "disable", "default"):
        p = account_sub.add_parser(action, help=f"{action} a configured account")
        p.add_argument("name")

    account_remove = account_sub.add_parser("remove", help="remove an account from tgharness")
    account_remove.add_argument("name")
    account_remove.add_argument(
        "--delete-session",
        action="store_true",
        help="also delete that local .session and journal files; does not delete the Telegram account",
    )

    account_info = account_sub.add_parser("info", help="get live identity/profile details for an account")
    account_info.add_argument("name", nargs="?", help="defaults to the configured default account")
    account_info.add_argument("--photos", type=int, default=0, help="include metadata for up to N profile photos")
    account_info.add_argument("--download-photos", action="store_true", help="download included profile photos for agent vision")

    account_photos = account_sub.add_parser("photos", help="list or download profile photos for an account")
    account_photos.add_argument("name", nargs="?", help="defaults to the configured default account")
    account_photos.add_argument("--limit", type=int, default=5)
    account_photos.add_argument("--download", action="store_true", help="download files and return local paths")

    methods = sub.add_parser("methods", help="list public PyroTGFork Client methods")
    methods.add_argument("query", nargs="?", help="optional name filter")

    describe = sub.add_parser("describe", help="inspect a PyroTGFork Client method at runtime")
    describe.add_argument("method")

    call = sub.add_parser("call", help="invoke any public PyroTGFork Client method")
    call.add_argument("method")
    call.add_argument("--params", type=_json_object, default={}, help="JSON object of keyword arguments")
    call.add_argument("--collect-limit", type=int, help="maximum items collected from a generator; -1 means unlimited")

    raw = sub.add_parser("raw", help="invoke a raw Telegram API function exposed by PyroTGFork")
    raw.add_argument("function", help="dotted raw function name, e.g. messages.GetHistory")
    raw.add_argument("--params", type=_json_object, default={}, help="JSON object used to construct the raw function")
    raw.add_argument("--retries", type=int, default=0)
    raw.add_argument("--timeout", type=float)
    raw.add_argument("--sleep-threshold", type=float)

    python_cmd = sub.add_parser("python", aliases=["exec"], help="execute a stateful async PyroTGFork Python snippet")
    python_cmd.add_argument("code")

    sub.add_parser("me", help="get the current Telegram identity")

    dialogs = sub.add_parser("dialogs", help="list dialogs")
    dialogs.add_argument("--limit", type=int, default=20)

    history = sub.add_parser("history", help="read chat history")
    history.add_argument("chat_id", type=_chat_id)
    history.add_argument("--limit", type=int, default=20)
    history.add_argument("--min-id", type=int, default=0)
    history.add_argument("--max-id", type=int, default=0)
    history.add_argument("--reverse", action="store_true")
    history.add_argument("--scheduled", action="store_true")

    get_messages = sub.add_parser("get-messages", help="get one or more messages")
    get_messages.add_argument("message_ids", type=_message_ids)
    get_messages.add_argument("--chat", dest="chat_id", type=_chat_id)
    get_messages.add_argument("--replies", type=int, default=1)

    send = sub.add_parser("send", help="send a text message")
    send.add_argument("chat_id", type=_chat_id)
    send.add_argument("text")
    send.add_argument("--reply-to", dest="reply_to_message_id", type=int)
    send.add_argument("--silent", dest="disable_notification", action="store_true")

    media = sub.add_parser("send-media", help="send a common media type; use call for every other send method")
    media.add_argument("media_type", choices=["photo", "audio", "document", "video", "animation", "voice", "video_note", "sticker"])
    media.add_argument("chat_id", type=_chat_id)
    media.add_argument("file")
    media.add_argument("--caption")
    media.add_argument("--reply-to", dest="reply_to_message_id", type=int)

    upload = sub.add_parser("upload", help="upload and send a generic file as a Telegram document")
    upload.add_argument("chat_id", type=_chat_id)
    upload.add_argument("file")
    upload.add_argument("--caption")
    upload.add_argument("--reply-to", dest="reply_to_message_id", type=int)
    upload.add_argument("--silent", dest="disable_notification", action="store_true")

    download = sub.add_parser("download", help="download media from a message")
    download.add_argument("chat_id", type=_chat_id)
    download.add_argument("message_id", type=int)
    download.add_argument("--file-name")

    edit = sub.add_parser("edit", help="edit message text")
    edit.add_argument("chat_id", type=_chat_id)
    edit.add_argument("message_id", type=int)
    edit.add_argument("text")

    delete = sub.add_parser("delete", help="delete one or more messages")
    delete.add_argument("chat_id", type=_chat_id)
    delete.add_argument("message_ids", type=_message_ids)
    delete.add_argument("--local-only", dest="revoke", action="store_false", default=True)
    delete.add_argument("--scheduled", dest="is_scheduled", action="store_true")

    forward = sub.add_parser("forward", help="forward one or more messages")
    forward.add_argument("chat_id", type=_chat_id)
    forward.add_argument("from_chat_id", type=_chat_id)
    forward.add_argument("message_ids", type=_message_ids)
    forward.add_argument("--silent", dest="disable_notification", action="store_true")

    copy = sub.add_parser("copy", help="copy a message without linking to the original")
    copy.add_argument("chat_id", type=_chat_id)
    copy.add_argument("from_chat_id", type=_chat_id)
    copy.add_argument("message_id", type=int)

    search = sub.add_parser("search", help="search messages in a chat")
    search.add_argument("chat_id", type=_chat_id)
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--limit", type=int, default=20)

    get_chat = sub.add_parser("get-chat", help="get up-to-date chat information")
    get_chat.add_argument("chat_id", type=_chat_id)

    join = sub.add_parser("join", help="join a group or channel")
    join.add_argument("chat_id", type=_chat_id)

    leave = sub.add_parser("leave", help="leave a group or channel")
    leave.add_argument("chat_id", type=_chat_id)
    leave.add_argument("--delete", action="store_true")

    return parser


def _command_args(namespace: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    command = namespace.command
    if command == "exec":
        command = "python"
    raw = vars(namespace).copy()
    for key in {
        "command",
        "direct",
        "compact",
        "request_id",
        "account",
        "accounts",
        "all_accounts",
        "account_command",
    }:
        raw.pop(key, None)
    if command == "methods":
        return command, {"query": raw.get("query")}
    if command == "describe":
        return command, {"method": raw["method"]}
    if command == "call":
        return command, {"method": raw["method"], "params": raw["params"], "collect_limit": raw.get("collect_limit")}
    if command == "raw":
        return command, raw
    if command == "python":
        return command, {"code": raw["code"]}
    if command == "dialogs":
        return command, {"limit": raw["limit"]}
    if command == "history":
        raw["is_scheduled"] = raw.pop("scheduled")
    return command.replace("-", "_"), raw


def _selected_accounts(namespace: argparse.Namespace) -> tuple[list[str] | None, bool]:
    if namespace.account:
        return [namespace.account], False
    if namespace.accounts:
        return namespace.accounts, False
    return None, bool(namespace.all_accounts)


async def _serve() -> None:
    pool = AccountPool(config)
    startup = await pool.start_enabled()
    server = HarnessIPCServer(pool, dispatch_request)
    await server.start()
    ready = {
        "ok": True,
        "data": {
            "status": "ready",
            "socket": str(server.socket_path),
            "accounts": pool.status(),
            "startup": startup,
        },
        "error": None,
        "meta": {"transport": "ipc-server"},
    }
    print(dumps(ready, pretty=config.pretty_json), flush=True)
    try:
        await server.serve_forever()
    finally:
        await server.stop()
        await pool.close()


async def _dispatch_with_transport(
    command: str,
    args: dict[str, Any],
    *,
    namespace: argparse.Namespace,
    account_names: list[str] | None = None,
    all_accounts: bool = False,
) -> dict[str, Any]:
    request_id = namespace.request_id or str(uuid.uuid4())
    response = None
    if not namespace.direct:
        try:
            ipc_response = await send_ipc_command(
                command,
                args,
                request_id=request_id,
                account_names=account_names,
                all_accounts=all_accounts,
            )
            if ipc_response.get("transport_available", True):
                response = ipc_response
        except (ConnectionError, FileNotFoundError, asyncio.TimeoutError, OSError):
            response = None

    if response is None:
        direct_cfg = Config()
        pool = AccountPool(direct_cfg, persistent=False)
        try:
            response = await dispatch_request(
                pool,
                command,
                args,
                request_id=request_id,
                account_names=account_names,
                all_accounts=all_accounts,
            )
            response.setdefault("meta", {})["transport"] = "direct"
        finally:
            await pool.close()
    return response


async def _run_account_command(namespace: argparse.Namespace) -> int:
    action = namespace.account_command
    if action == "login":
        active = Config()
        name = namespace.name or active.default_account
        await login_interactive(cfg=active, phone=namespace.phone, account=name)
        return 0

    if action == "add":
        # When immediate login is requested, keep the new account disabled until authorization is complete.
        desired_enabled = not namespace.disabled
        response = await _dispatch_with_transport(
            "account_add",
            {
                "name": namespace.name,
                "session_name": namespace.session_name,
                "enabled": False if namespace.login else desired_enabled,
                "make_default": namespace.make_default and not namespace.login,
            },
            namespace=namespace,
        )
        if not response.get("ok"):
            print(dumps(response, pretty=not namespace.compact and config.pretty_json))
            return 1

        if namespace.login:
            refreshed = Config()
            await login_interactive(cfg=refreshed, phone=namespace.phone, account=namespace.name)
            if desired_enabled:
                response = await _dispatch_with_transport(
                    "account_enable",
                    {"name": namespace.name},
                    namespace=namespace,
                )
            if namespace.make_default and response.get("ok"):
                response = await _dispatch_with_transport(
                    "account_default",
                    {"name": namespace.name},
                    namespace=namespace,
                )
        print(dumps(response, pretty=not namespace.compact and config.pretty_json))
        return 0 if response.get("ok") else 1

    mapping = {
        "list": ("account_list", {}),
        "enable": ("account_enable", {"name": getattr(namespace, "name", None)}),
        "disable": ("account_disable", {"name": getattr(namespace, "name", None)}),
        "default": ("account_default", {"name": getattr(namespace, "name", None)}),
        "remove": (
            "account_remove",
            {"name": getattr(namespace, "name", None), "delete_session": getattr(namespace, "delete_session", False)},
        ),
        "info": (
            "account_info",
            {
                "name": getattr(namespace, "name", None),
                "photo_limit": max(
                    1 if getattr(namespace, "download_photos", False) else 0,
                    getattr(namespace, "photos", 0),
                ),
                "download_photos": getattr(namespace, "download_photos", False),
            },
        ),
        "photos": (
            "account_photos",
            {
                "name": getattr(namespace, "name", None),
                "limit": max(1, getattr(namespace, "limit", 5)),
                "download": getattr(namespace, "download", False),
            },
        ),
    }
    command, args = mapping[action]
    account_names = None
    all_accounts = False
    if action in {"info", "photos"}:
        account_names, all_accounts = _selected_accounts(namespace)
        if getattr(namespace, "name", None) and (account_names or all_accounts):
            response = {
                "ok": False,
                "data": None,
                "error": {
                    "type": "ValueError",
                    "message": "Use either an account name or --account/--accounts/--all-accounts, not both",
                },
                "meta": {"operation": command},
            }
            print(dumps(response, pretty=not namespace.compact and config.pretty_json))
            return 1
    response = await _dispatch_with_transport(
        command,
        args,
        namespace=namespace,
        account_names=account_names,
        all_accounts=all_accounts,
    )
    print(dumps(response, pretty=not namespace.compact and config.pretty_json))
    return 0 if response.get("ok") else 1


async def _run(namespace: argparse.Namespace) -> int:
    if namespace.command == "setup":
        cfg = setup_interactive(
            api_id=namespace.api_id,
            api_hash=namespace.api_hash,
            session_name=namespace.session_name,
            workdir=namespace.workdir,
        )
        if not namespace.no_login:
            await login_interactive(cfg=cfg, phone=namespace.phone, account=cfg.default_account)
        return 0

    if namespace.command == "login":
        chosen = namespace.login_account or namespace.account or Config().default_account
        await login_interactive(phone=namespace.phone, account=chosen)
        return 0

    if namespace.command == "serve":
        await _serve()
        return 0

    if namespace.command in {"account", "accounts"}:
        return await _run_account_command(namespace)

    command, args = _command_args(namespace)
    selected, all_accounts = _selected_accounts(namespace)
    response = await _dispatch_with_transport(
        command,
        args,
        namespace=namespace,
        account_names=selected,
        all_accounts=all_accounts,
    )
    print(dumps(response, pretty=not namespace.compact and config.pretty_json))
    return 0 if response.get("ok") else 1


def main() -> None:
    parser = build_parser()
    namespace = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(_run(namespace)))
    except KeyboardInterrupt:
        raise SystemExit(130)


if __name__ == "__main__":
    main()
