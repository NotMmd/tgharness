import asyncio
import inspect
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable

from pyrogram import Client

from .config import Config, config


def get_client(*, cfg: Config | None = None, **overrides: Any) -> Client:
    active = cfg or config
    active.validate()
    kwargs: dict[str, Any] = {
        "name": active.session_name,
        "api_id": active.api_id,
        "api_hash": active.api_hash,
        "workdir": str(active.workdir),
        "in_memory": active.in_memory,
        "no_updates": active.no_updates,
        "sleep_threshold": active.sleep_threshold,
    }
    if active.bot_token:
        kwargs["bot_token"] = active.bot_token
    if active.proxy:
        kwargs["proxy"] = active.proxy
    kwargs.update(overrides)
    return Client(**kwargs)


@asynccontextmanager
async def tg_session(**client_kwargs: Any):
    app = get_client(**client_kwargs)
    async with app:
        yield app


def run_tg(func: Callable[[Client], Awaitable[Any] | Any]) -> Any:
    async def runner() -> Any:
        async with tg_session() as app:
            result = func(app)
            if inspect.isawaitable(result):
                return await result
            return result

    return asyncio.run(runner())
