import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


async def call_with_retry(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    max_retries: int = 3,
    network_backoff_base: float = 2.0,
    **kwargs: Any,
) -> Any:
    from pyrogram.errors import FloodWait

    attempt = 0
    while True:
        try:
            return await func(*args, **kwargs)
        except FloodWait as exc:
            attempt += 1
            if attempt > max_retries:
                raise
            await asyncio.sleep(float(exc.value) + 1.0)
        except (ConnectionError, TimeoutError):
            attempt += 1
            if attempt > max_retries:
                raise
            await asyncio.sleep(min(30.0, network_backoff_base ** attempt))
