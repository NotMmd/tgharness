import asyncio
from pathlib import Path
from typing import Any

from .client import start_authorized_client, stop_client
from .config import AccountConfig, Config, config
from .serialization import to_jsonable


class AccountPool:
    """Own one live PyroTGFork Client per configured tgharness account."""

    def __init__(self, cfg: Config | None = None, *, persistent: bool = True):
        self.config = cfg or config
        self.persistent = persistent
        self.clients: dict[str, Any] = {}
        self.start_errors: dict[str, str] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, name: str) -> asyncio.Lock:
        return self._locks.setdefault(name, asyncio.Lock())

    async def _stop_unlocked(self, name: str) -> bool:
        app = self.clients.pop(name, None)
        if app is None:
            return False
        await stop_client(app)
        return True

    async def start(self, name: str, *, allow_disabled: bool = False) -> Any:
        async with self._lock(name):
            account_cfg = self.config.account(name, allow_disabled=allow_disabled)
            if name in self.clients:
                return self.clients[name]
            for live_name in self.clients:
                live_cfg = self.config.account(live_name, allow_disabled=True)
                if live_cfg.session_file == account_cfg.session_file:
                    raise RuntimeError(
                        f"Accounts '{live_name}' and '{name}' resolve to the same session file. "
                        "A file-backed PyroTGFork session cannot be owned by two live clients at once."
                    )
            try:
                app = await start_authorized_client(
                    cfg=self.config,
                    account=account_cfg.name,
                    allow_disabled=allow_disabled,
                )
            except Exception as exc:
                self.start_errors[name] = f"{type(exc).__name__}: {exc}"
                raise
            self.clients[name] = app
            self.start_errors.pop(name, None)
            return app

    async def start_enabled(self) -> dict[str, str | None]:
        results: dict[str, str | None] = {}
        for name in self.config.account_names(enabled_only=True):
            try:
                await self.start(name)
            except Exception as exc:
                results[name] = f"{type(exc).__name__}: {exc}"
            else:
                results[name] = None
        return results

    async def get(self, name: str) -> Any:
        self.config.account(name)  # validate enabled + existence
        if name in self.clients:
            return self.clients[name]
        return await self.start(name)

    async def stop(self, name: str) -> bool:
        async with self._lock(name):
            return await self._stop_unlocked(name)

    async def enable(self, name: str) -> dict[str, Any]:
        account_cfg = self.config.set_account_enabled(name, True)
        started = False
        error = None
        if self.persistent:
            try:
                await self.start(name)
                started = True
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        return {
            **account_cfg.public_dict(default=name == self.config.default_account),
            "runtime_active": started,
            "runtime_error": error,
        }

    async def disable(self, name: str) -> dict[str, Any]:
        async with self._lock(name):
            account_cfg = self.config.set_account_enabled(name, False)
            stopped = await self._stop_unlocked(name)
            self.start_errors.pop(name, None)
        return {
            **account_cfg.public_dict(default=name == self.config.default_account),
            "runtime_active": False,
            "runtime_stopped": stopped,
        }

    async def remove(self, name: str, *, delete_session: bool = False) -> dict[str, Any]:
        async with self._lock(name):
            removed = self.config.remove_account(name)
            await self._stop_unlocked(name)
            self.start_errors.pop(name, None)
        deleted: list[str] = []
        if delete_session:
            for suffix in (".session", ".session-journal", ".session-shm", ".session-wal"):
                path = Path(str(removed.session_path) + suffix)
                if path.exists():
                    path.unlink()
                    deleted.append(str(path))
        return {
            "account": removed.public_dict(default=False),
            "deleted_session_files": deleted,
        }

    def status(self) -> list[dict[str, Any]]:
        result = []
        for item in self.config.public_accounts():
            name = item["name"]
            item["runtime_active"] = name in self.clients
            item["runtime_error"] = self.start_errors.get(name)
            result.append(item)
        return result

    async def close(self) -> None:
        for name in list(self.clients):
            await self.stop(name)


async def account_identity(
    app: Any,
    account_cfg: AccountConfig,
    *,
    include_photos: bool = False,
    photo_limit: int = 5,
    download_photos: bool = False,
    download_root: Path | None = None,
) -> dict[str, Any]:
    """Return live identity/profile information for one authorized account."""
    user = await app.get_me()
    photo_count = await app.get_chat_photos_count("me")

    chat = None
    try:
        chat = await app.get_chat("me")
    except Exception:
        # get_me remains authoritative for identity even if full chat lookup is unavailable.
        chat = None

    result: dict[str, Any] = {
        "account": account_cfg.public_dict(),
        "identity": to_jsonable(user),
        "profile": to_jsonable(chat) if chat is not None else None,
        "profile_photo_count": int(photo_count),
    }

    if include_photos or download_photos:
        limit = max(0, int(photo_limit))
        photos: list[dict[str, Any]] = []
        root = (download_root or account_cfg.workdir / "downloads" / "profiles" / account_cfg.name).expanduser().resolve()
        if download_photos and limit > 0:
            root.mkdir(parents=True, exist_ok=True)
        if limit > 0:
            index = 0
            async for photo in app.get_chat_photos("me", limit=limit):
                entry: dict[str, Any] = {
                    "index": index,
                    "media": to_jsonable(photo),
                    "path": None,
                }
                if download_photos:
                    path = await app.download_media(photo, file_name=str(root) + "/", in_memory=False)
                    entry["path"] = path
                photos.append(entry)
                index += 1
        result["profile_photos"] = photos
        result["profile_photos_returned"] = len(photos)
        result["profile_photos_downloaded"] = bool(download_photos)

    return result
