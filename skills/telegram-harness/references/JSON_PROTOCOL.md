# JSON protocol

## Envelope

Success:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "uuid-or-agent-id",
    "operation": "method",
    "duration_ms": 4.2,
    "transport": "ipc"
  }
}
```

Failure:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "type": "SomeRPCError",
    "message": "..."
  },
  "meta": {
    "request_id": "...",
    "operation": "method",
    "duration_ms": 4.2,
    "transport": "direct"
  }
}
```

`FloodWait` errors may additionally contain `error.retry_after` and the RPC error's value fields.

## Tagged input values

The generic `call` and `raw` gateways recursively decode tagged values.

### Enum

```json
{"$enum":"ParseMode.MARKDOWN"}
```

Resolution root: `pyrogram.enums`.

Nested enum classes are supported through dotted class paths.

### PyroTGFork type

```json
{
  "$type":"InlineKeyboardButton",
  "kwargs": {
    "text":"Open",
    "url":"https://example.com"
  }
}
```

Resolution root: `pyrogram.types`.

### Raw type

```json
{
  "$raw_type":"InputPeerSelf",
  "kwargs": {}
}
```

Resolution root: `pyrogram.raw.types`.

Nested raw namespaces can be written as dotted paths when PyroTGFork exposes them that way.

### Embedded Raw function

```json
{
  "$raw_function":"messages.GetHistory",
  "kwargs": {}
}
```

Resolution root: `pyrogram.raw.functions`.

### Datetime

```json
{"$datetime":"2026-09-01T12:30:00+03:30"}
```

Use ISO 8601. `Z` is accepted and normalized to UTC.

### Bytes

```json
{"$bytes_base64":"SGVsbG8="}
```

### Tuple

```json
{"$tuple":[1,2,3]}
```

## Nested construction

Tags can be nested recursively, for example:

```json
{
  "$type":"InlineKeyboardMarkup",
  "kwargs": {
    "inline_keyboard": [[
      {
        "$type":"InlineKeyboardButton",
        "kwargs": {
          "text":"Open",
          "url":"https://example.com"
        }
      }
    ]]
  }
}
```

## Output serialization

The serializer handles:

- JSON primitives unchanged
- `bytes` / `bytearray` as `$bytes_base64`
- `datetime`, `date`, and `time` as ISO strings
- `Path` as string
- enums by value
- mappings and iterables recursively
- dataclasses recursively
- PyroTGFork objects by parsing their JSON-like `str(obj)` representation when possible
- otherwise, public attributes from `__dict__`
- final fallback to `str(value)`

Recursive object graphs are protected from infinite recursion.

## Generators

Client methods returning async or sync generators are collected into arrays. Metadata contains:

```json
{
  "collected": 100,
  "truncated": true,
  "collect_limit": 100
}
```

Never claim completeness when `truncated` is true.

## IPC wire format

The Unix socket uses newline-delimited JSON: one request object and one response envelope per connection.

Request:

```json
{
  "request_id":"...",
  "command":"call",
  "args":{
    "method":"get_users",
    "params":{"user_ids":["me"]}
  }
}
```

The server delegates the command to the same gateway used by direct CLI execution, so direct and IPC responses share the same envelope.
