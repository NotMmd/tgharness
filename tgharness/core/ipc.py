import asyncio
import json
import os
from pathlib import Path
from typing import Any, Awaitable, Callable

from .config import config


class HarnessIPCServer:
    def __init__(self, client: Any, handler: Callable[..., Awaitable[dict]], socket_path: str | Path | None = None):
        self.client = client
        self.handler = handler
        self.socket_path = Path(socket_path or config.ipc_socket)
        self.server: asyncio.AbstractServer | None = None
        self._owns_socket = False

    async def start(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_unix_connection(path=str(self.socket_path)),
                    timeout=0.5,
                )
            except (ConnectionRefusedError, FileNotFoundError):
                self.socket_path.unlink(missing_ok=True)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(f"IPC socket liveness check timed out at {self.socket_path}") from exc
            else:
                writer.close()
                await writer.wait_closed()
                raise RuntimeError(f"IPC server already active at {self.socket_path}")
        self.server = await asyncio.start_unix_server(self._handle, path=str(self.socket_path))
        os.chmod(self.socket_path, 0o600)
        self._owns_socket = True

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            line = await asyncio.wait_for(reader.readline(), timeout=config.ipc_timeout)
            if not line:
                return
            request = json.loads(line.decode("utf-8"))
            response = await self.handler(
                self.client,
                request.get("command", ""),
                request.get("args") or {},
                request_id=request.get("request_id"),
            )
            writer.write((json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
            await writer.drain()
        except Exception as exc:
            response = {
                "ok": False,
                "data": None,
                "error": {"type": type(exc).__name__, "message": str(exc)},
                "meta": {"transport": "ipc"},
            }
            try:
                writer.write((json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
                await writer.drain()
            except (ConnectionError, BrokenPipeError):
                pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, BrokenPipeError):
                pass

    async def serve_forever(self) -> None:
        if self.server is None:
            await self.start()
        assert self.server is not None
        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        if self._owns_socket and self.socket_path.exists():
            self.socket_path.unlink()
        self._owns_socket = False


async def send_ipc_command(command: str, args: dict | None = None, *, timeout: float | None = None, request_id: str | None = None) -> dict:
    socket_path = config.ipc_socket
    if not socket_path.exists():
        return {"transport_available": False}
    reader, writer = await asyncio.open_unix_connection(path=str(socket_path))
    try:
        payload = {
            "request_id": request_id,
            "command": command,
            "args": args or {},
        }
        writer.write((json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8"))
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=timeout or config.ipc_timeout)
        if not line:
            raise RuntimeError("Empty IPC response")
        response = json.loads(line.decode("utf-8"))
        response.setdefault("meta", {})["transport"] = "ipc"
        return response
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, BrokenPipeError):
            pass
