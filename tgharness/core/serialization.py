import base64
import dataclasses
import json
from datetime import date, datetime, time
from enum import Enum
from pathlib import Path
from typing import Any


def to_jsonable(value: Any, *, _seen: set[int] | None = None) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"$bytes_base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, bytearray):
        return {"$bytes_base64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value

    if _seen is None:
        _seen = set()
    obj_id = id(value)
    if obj_id in _seen:
        return f"<{type(value).__name__}:recursive>"
    _seen.add(obj_id)

    try:
        if isinstance(value, dict):
            return {str(k): to_jsonable(v, _seen=_seen) for k, v in value.items()}
        if isinstance(value, (list, tuple, set, frozenset)):
            return [to_jsonable(v, _seen=_seen) for v in value]
        if dataclasses.is_dataclass(value):
            return to_jsonable(dataclasses.asdict(value), _seen=_seen)

        try:
            rendered = str(value)
            if rendered and rendered[0] in "[{":
                parsed = json.loads(rendered)
                return to_jsonable(parsed, _seen=_seen)
        except (TypeError, ValueError, json.JSONDecodeError):
            pass

        attrs = getattr(value, "__dict__", None)
        if isinstance(attrs, dict):
            public = {k: v for k, v in attrs.items() if not k.startswith("_")}
            if public:
                result = to_jsonable(public, _seen=_seen)
                if isinstance(result, dict):
                    result.setdefault("_type", type(value).__name__)
                return result

        return str(value)
    finally:
        _seen.discard(obj_id)


def dumps(value: Any, *, pretty: bool = True) -> str:
    return json.dumps(
        to_jsonable(value),
        ensure_ascii=False,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )
