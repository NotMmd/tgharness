import ast
import asyncio
import base64
import importlib
import inspect
import json
import time
import uuid
from datetime import datetime
from typing import Any

from .config import config
from .serialization import to_jsonable

DOCS_BASE = "https://telegramplayground.github.io/pyrogram/"


def envelope(data: Any = None, *, request_id: str | None = None, meta: dict | None = None) -> dict:
    return {
        "ok": True,
        "data": to_jsonable(data),
        "error": None,
        "meta": {"request_id": request_id or str(uuid.uuid4()), **(meta or {})},
    }


def error_envelope(exc: Exception, *, request_id: str | None = None, operation: str | None = None) -> dict:
    error: dict[str, Any] = {
        "type": type(exc).__name__,
        "message": str(exc),
    }
    value = getattr(exc, "value", None)
    if value is not None:
        error["value"] = to_jsonable(value)
        if type(exc).__name__ == "FloodWait":
            error["retry_after"] = value
    x = getattr(exc, "x", None)
    if x is not None:
        error["x"] = to_jsonable(x)
    return {
        "ok": False,
        "data": None,
        "error": error,
        "meta": {
            "request_id": request_id or str(uuid.uuid4()),
            **({"operation": operation} if operation else {}),
        },
    }


def _resolve_attr(root: Any, dotted: str) -> Any:
    current = root
    for part in dotted.split("."):
        if not part or part.startswith("_"):
            raise ValueError(f"Invalid symbol path: {dotted}")
        current = getattr(current, part)
    return current


def _resolve_pyrogram(namespace: str, dotted: str) -> Any:
    module = importlib.import_module(f"pyrogram.{namespace}")
    return _resolve_attr(module, dotted)


def decode_value(value: Any) -> Any:
    if isinstance(value, list):
        return [decode_value(item) for item in value]
    if not isinstance(value, dict):
        return value

    if set(value) == {"$datetime"}:
        return datetime.fromisoformat(str(value["$datetime"]).replace("Z", "+00:00"))
    if set(value) == {"$bytes_base64"}:
        return base64.b64decode(value["$bytes_base64"])
    if set(value) == {"$tuple"}:
        return tuple(decode_value(item) for item in value["$tuple"])
    if "$enum" in value:
        enum_cls, member = str(value["$enum"]).rsplit(".", 1)
        return getattr(_resolve_pyrogram("enums", enum_cls), member)
    if "$type" in value:
        cls = _resolve_pyrogram("types", str(value["$type"]))
        kwargs = decode_value(value.get("kwargs", {}))
        return cls(**kwargs)
    if "$raw_type" in value:
        cls = _resolve_pyrogram("raw.types", str(value["$raw_type"]))
        kwargs = decode_value(value.get("kwargs", {}))
        return cls(**kwargs)
    if "$raw_function" in value:
        cls = _resolve_pyrogram("raw.functions", str(value["$raw_function"]))
        kwargs = decode_value(value.get("kwargs", {}))
        return cls(**kwargs)
    return {key: decode_value(item) for key, item in value.items()}


async def collect_result(result: Any, limit: int | None = None) -> tuple[Any, dict]:
    if inspect.isawaitable(result):
        result = await result

    if hasattr(result, "__aiter__"):
        cap = config.collect_limit if limit is None else limit
        items = []
        truncated = False
        async for item in result:
            if cap >= 0 and len(items) >= cap:
                truncated = True
                break
            items.append(item)
        return items, {"collected": len(items), "truncated": truncated, "collect_limit": cap}

    if inspect.isgenerator(result):
        cap = config.collect_limit if limit is None else limit
        items = []
        truncated = False
        for item in result:
            if cap >= 0 and len(items) >= cap:
                truncated = True
                break
            items.append(item)
        return items, {"collected": len(items), "truncated": truncated, "collect_limit": cap}

    return result, {}


def list_client_methods(app: Any, query: str | None = None) -> list[dict]:
    items = []
    needle = query.lower() if query else None
    for name in dir(app):
        if name.startswith("_"):
            continue
        value = getattr(app, name, None)
        if not callable(value):
            continue
        if needle and needle not in name.lower():
            continue
        try:
            signature = str(inspect.signature(value))
        except (TypeError, ValueError):
            signature = None
        doc = inspect.getdoc(value) or ""
        items.append({
            "name": name,
            "signature": signature,
            "summary": doc.splitlines()[0] if doc else None,
            "docs": f"{DOCS_BASE}api/methods/{name}.html",
        })
    return items


def describe_client_method(app: Any, name: str) -> dict:
    if not name or name.startswith("_"):
        raise ValueError("Only public Client methods can be described")
    method = getattr(app, name, None)
    if not callable(method):
        raise AttributeError(f"PyroTGFork Client has no callable method: {name}")
    try:
        signature = str(inspect.signature(method))
    except (TypeError, ValueError):
        signature = None
    return {
        "name": name,
        "signature": signature,
        "docstring": inspect.getdoc(method),
        "docs": f"{DOCS_BASE}api/methods/{name}.html",
    }


async def call_client_method(app: Any, method_name: str, params: dict | None = None, collect_limit: int | None = None) -> tuple[Any, dict]:
    if not method_name or method_name.startswith("_"):
        raise ValueError("Only public PyroTGFork Client methods may be called")
    method = getattr(app, method_name, None)
    if not callable(method):
        raise AttributeError(f"PyroTGFork Client has no callable method: {method_name}")
    decoded = decode_value(params or {})
    if not isinstance(decoded, dict):
        raise TypeError("params must decode to a JSON object")
    result = method(**decoded)
    return await collect_result(result, collect_limit)


async def invoke_raw(app: Any, function: str, params: dict | None = None, *, retries: int = 0, timeout: float | None = None, sleep_threshold: float | None = None) -> Any:
    query_cls = _resolve_pyrogram("raw.functions", function)
    decoded = decode_value(params or {})
    if not isinstance(decoded, dict):
        raise TypeError("raw params must decode to a JSON object")
    query = query_cls(**decoded)
    kwargs: dict[str, Any] = {"retries": retries}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if sleep_threshold is not None:
        kwargs["sleep_threshold"] = sleep_threshold
    return await app.invoke(query, **kwargs)


async def execute_python(app: Any, code: str) -> Any:
    pyrogram = importlib.import_module("pyrogram")
    scope = {
        "app": app,
        "pyrogram": pyrogram,
        "types": importlib.import_module("pyrogram.types"),
        "enums": importlib.import_module("pyrogram.enums"),
        "filters": importlib.import_module("pyrogram.filters"),
        "handlers": importlib.import_module("pyrogram.handlers"),
        "raw": importlib.import_module("pyrogram.raw"),
        "asyncio": asyncio,
        "json": json,
    }
    stripped = code.strip()
    if not stripped:
        return None
    lines = stripped.splitlines()
    tree = ast.parse(stripped, mode="exec")
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
        expression = ast.get_source_segment(stripped, tree.body[0].value) or ast.unparse(tree.body[0].value)
        body = f"    return {expression}"
    else:
        body = "\n".join(f"    {line}" for line in lines)
    exec(f"async def __tgharness_exec():\n{body}", scope)
    return await scope["__tgharness_exec"]()


async def dispatch(app: Any, command: str, args: dict | None = None, *, request_id: str | None = None) -> dict:
    args = args or {}
    started = time.monotonic()
    try:
        if command == "methods":
            data = list_client_methods(app, args.get("query"))
            meta = {"count": len(data)}
        elif command == "describe":
            data = describe_client_method(app, args["method"])
            meta = {}
        elif command == "call":
            data, meta = await call_client_method(app, args["method"], args.get("params"), args.get("collect_limit"))
        elif command == "raw":
            data = await invoke_raw(
                app,
                args["function"],
                args.get("params"),
                retries=int(args.get("retries", 0)),
                timeout=args.get("timeout"),
                sleep_threshold=args.get("sleep_threshold"),
            )
            meta = {"raw": True}
        elif command == "python":
            data = await execute_python(app, args["code"])
            meta = {"unsafe_python": True}
        else:
            data, meta = await dispatch_convenience(app, command, args)
        meta["operation"] = command
        meta["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        return envelope(data, request_id=request_id, meta=meta)
    except Exception as exc:
        result = error_envelope(exc, request_id=request_id, operation=command)
        result["meta"]["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        return result


async def dispatch_convenience(app: Any, command: str, args: dict) -> tuple[Any, dict]:
    if command == "me":
        return await app.get_me(), {}
    if command == "dialogs":
        return await collect_result(app.get_dialogs(limit=args.get("limit", 20)), args.get("limit", 20))
    if command == "history":
        return await collect_result(
            app.get_chat_history(
                args["chat_id"],
                limit=args.get("limit", 20),
                min_id=args.get("min_id", 0),
                max_id=args.get("max_id", 0),
                reverse=args.get("reverse", False),
                is_scheduled=args.get("is_scheduled", False),
            ),
            args.get("limit", 20),
        )
    if command == "get_messages":
        params = {"message_ids": args["message_ids"], "replies": args.get("replies", 1)}
        if args.get("chat_id") is not None:
            params["chat_id"] = args["chat_id"]
        return await app.get_messages(**params), {}
    if command == "send":
        return await app.send_message(
            args["chat_id"],
            args["text"],
            reply_to_message_id=args.get("reply_to_message_id"),
            disable_notification=args.get("disable_notification", False),
        ), {}
    if command == "send_media":
        media_type = args["media_type"]
        allowed = {"photo", "audio", "document", "video", "animation", "voice", "video_note", "sticker"}
        if media_type not in allowed:
            raise ValueError(f"Unsupported convenience media type: {media_type}. Use 'call' for other PyroTGFork methods.")
        method = getattr(app, f"send_{media_type}")
        kwargs = {
            "chat_id": args["chat_id"],
            media_type if media_type != "video_note" else "video_note": args["file"],
        }
        if args.get("caption") is not None and media_type not in {"sticker", "video_note"}:
            kwargs["caption"] = args["caption"]
        if args.get("reply_to_message_id") is not None:
            kwargs["reply_to_message_id"] = args["reply_to_message_id"]
        return await method(**kwargs), {}
    if command == "upload":
        return await app.send_document(
            args["chat_id"],
            args["file"],
            caption=args.get("caption"),
            reply_to_message_id=args.get("reply_to_message_id"),
            disable_notification=args.get("disable_notification", False),
        ), {}
    if command == "download":
        message = await app.get_messages(
            chat_id=args["chat_id"],
            message_ids=args["message_id"],
            replies=0,
        )
        file_name = args.get("file_name") or str(config.download_dir) + "/"
        path = await app.download_media(message, file_name=file_name, in_memory=False)
        return {"path": path, "chat_id": args["chat_id"], "message_id": args["message_id"]}, {}
    if command == "edit":
        return await app.edit_message_text(args["chat_id"], args["message_id"], args["text"]), {}
    if command == "delete":
        count = await app.delete_messages(
            args["chat_id"],
            args["message_ids"],
            revoke=args.get("revoke", True),
            is_scheduled=args.get("is_scheduled", False),
        )
        return {"affected": count}, {}
    if command == "forward":
        return await app.forward_messages(
            args["chat_id"],
            args["from_chat_id"],
            args["message_ids"],
            disable_notification=args.get("disable_notification", False),
        ), {}
    if command == "copy":
        return await app.copy_message(
            args["chat_id"],
            args["from_chat_id"],
            args["message_id"],
        ), {}
    if command == "search":
        return await collect_result(
            app.search_messages(args["chat_id"], query=args.get("query", ""), limit=args.get("limit", 20)),
            args.get("limit", 20),
        )
    if command == "get_chat":
        return await app.get_chat(args["chat_id"]), {}
    if command == "join":
        return await app.join_chat(args["chat_id"]), {}
    if command == "leave":
        return await app.leave_chat(args["chat_id"], delete=args.get("delete", False)), {}
    raise ValueError(f"Unknown harness command: {command}")
