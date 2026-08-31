import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

from . import __version__
from .core.auth import login_interactive, setup_interactive
from .core.client import tg_session
from .core.config import config
from .core.gateway import dispatch
from .core.ipc import HarnessIPCServer, send_ipc_command
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tgharness",
        description="Structured Telegram Agent Harness powered by PyroTGFork.",
    )
    parser.add_argument("--direct", action="store_true", help="bypass the IPC server and open the session directly")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument("--request-id", help="request ID to echo in the response envelope")
    parser.add_argument("--version", action="version", version=f"tgharness {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    setup = sub.add_parser("setup", help="configure Telegram credentials and optionally log in")
    setup.add_argument("--api-id", type=int)
    setup.add_argument("--api-hash", help="prefer the interactive prompt or TGHARNESS_API_HASH to avoid shell history")
    setup.add_argument("--session", dest="session_name")
    setup.add_argument("--workdir")
    setup.add_argument("--no-login", action="store_true")
    setup.add_argument("--phone")

    login = sub.add_parser("login", help="log in to a Telegram user account with code and 2FA hint support")
    login.add_argument("--phone")

    sub.add_parser("serve", help="hold one Telegram session and serve commands over the Unix socket")

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
    for key in {"command", "direct", "compact", "request_id"}:
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


async def _serve() -> None:
    async with tg_session() as app:
        server = HarnessIPCServer(app, dispatch)
        await server.start()
        ready = {
            "ok": True,
            "data": {"status": "ready", "socket": str(server.socket_path)},
            "error": None,
            "meta": {"transport": "ipc-server"},
        }
        print(dumps(ready, pretty=config.pretty_json), flush=True)
        try:
            await server.serve_forever()
        finally:
            await server.stop()


async def _run(namespace: argparse.Namespace) -> int:
    if namespace.command == "setup":
        cfg = setup_interactive(
            api_id=namespace.api_id,
            api_hash=namespace.api_hash,
            session_name=namespace.session_name,
            workdir=namespace.workdir,
        )
        if not namespace.no_login:
            await login_interactive(cfg=cfg, phone=namespace.phone)
        return 0

    if namespace.command == "login":
        await login_interactive(phone=namespace.phone)
        return 0

    if namespace.command == "serve":
        await _serve()
        return 0

    command, args = _command_args(namespace)
    request_id = namespace.request_id or str(uuid.uuid4())
    response = None

    if not namespace.direct:
        try:
            ipc_response = await send_ipc_command(command, args, request_id=request_id)
            if ipc_response.get("transport_available", True):
                response = ipc_response
        except (ConnectionError, FileNotFoundError, asyncio.TimeoutError, OSError):
            response = None

    if response is None:
        async with tg_session() as app:
            response = await dispatch(app, command, args, request_id=request_id)
            response.setdefault("meta", {})["transport"] = "direct"

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
