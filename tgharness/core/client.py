import asyncio
import inspect
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from pyrogram import Client

from .config import AccountConfig, Config, config


def get_client(
    *,
    cfg: Config | None = None,
    account: str | None = None,
    allow_disabled: bool = False,
    **overrides: Any,
) -> Client:
    active = cfg or config
    active.validate_credentials()
    account_cfg = active.account(account, allow_disabled=allow_disabled)
    account_cfg.workdir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "name": account_cfg.session_name,
        "api_id": active.api_id,
        "api_hash": active.api_hash,
        "workdir": str(account_cfg.workdir),
        "in_memory": account_cfg.in_memory,
        "no_updates": account_cfg.no_updates,
        "sleep_threshold": account_cfg.sleep_threshold,
    }
    if account_cfg.bot_token:
        kwargs["bot_token"] = account_cfg.bot_token
    if account_cfg.proxy:
        kwargs["proxy"] = account_cfg.proxy
    kwargs.update(overrides)
    return Client(**kwargs)


async def start_authorized_client(
    *,
    cfg: Config | None = None,
    account: str | None = None,
    allow_disabled: bool = False,
    **client_kwargs: Any,
) -> Client:
    """Start an existing authorized session without triggering PyroTGFork's interactive start wizard."""
    active = cfg or config
    account_cfg = active.account(account, allow_disabled=allow_disabled)
    app = get_client(cfg=active, account=account_cfg.name, allow_disabled=allow_disabled, **client_kwargs)
    connected = False
    try:
        authorized = await app.connect()
        connected = True
        if not authorized:
            raise RuntimeError(
                f"Account '{account_cfg.name}' is not authorized. Run `tgharness account login {account_cfg.name}`."
            )
        initialize = getattr(app, "initialize", None)
        if callable(initialize):
            await initialize()
        return app
    except Exception:
        if connected:
            try:
                await app.disconnect()
            except Exception:
                pass
        raise


async def stop_client(app: Client) -> None:
    stop = getattr(app, "stop", None)
    if callable(stop):
        try:
            await stop()
            return
        except ConnectionError:
            pass
    terminate = getattr(app, "terminate", None)
    if callable(terminate):
        try:
            await terminate()
        except (ConnectionError, RuntimeError):
            pass
    disconnect = getattr(app, "disconnect", None)
    if callable(disconnect):
        try:
            await disconnect()
        except ConnectionError:
            pass


@asynccontextmanager
async def tg_session(*, account: str | None = None, cfg: Config | None = None, **client_kwargs: Any):
    app = await start_authorized_client(cfg=cfg, account=account, **client_kwargs)
    try:
        yield app
    finally:
        await stop_client(app)


def run_tg(func: Callable[[Client], Awaitable[Any] | Any], *, account: str | None = None) -> Any:
    async def runner() -> Any:
        async with tg_session(account=account) as app:
            result = func(app)
            if inspect.isawaitable(result):
                return await result
            return result

    return asyncio.run(runner())
