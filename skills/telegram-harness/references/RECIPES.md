# Recipes

Use these as patterns, then verify unfamiliar signatures with `describe` and the PyroTGFork docs.

## Resolve a username

```bash
tgharness call get_users --params '{"user_ids":"@username"}'
```

For a chat/channel:

```bash
tgharness get-chat @username
```

## Read latest messages

```bash
tgharness history @chat --limit 25
```

For advanced filters or offsets:

```bash
tgharness call get_chat_history --params '{"chat_id":"@chat","limit":25}' --collect-limit 25
```

## Search photos containing a caption query

```bash
tgharness call search_messages --params '{
  "chat_id":"@chat",
  "query":"invoice",
  "filter":{"$enum":"MessagesFilter.PHOTO"},
  "limit":20
}' --collect-limit 20
```

## Send a document

```bash
tgharness call send_document --params '{
  "chat_id":"@chat",
  "document":"./report.pdf",
  "caption":"Report"
}'
```

## Send an inline keyboard

```bash
tgharness call send_message --params '{
  "chat_id":"@chat",
  "text":"Choose:",
  "reply_markup":{
    "$type":"InlineKeyboardMarkup",
    "kwargs":{
      "inline_keyboard":[[
        {"$type":"InlineKeyboardButton","kwargs":{"text":"Open","url":"https://example.com"}}
      ]]
    }
  }
}'
```

## Download media from a known message

```bash
tgharness download @chat 123 --file-name ./downloads/
```

## Iterate media as a stream

Use Python because the result is an async stream and may need incremental handling:

```bash
tgharness python $'message = await app.get_messages("@chat", 123)\nchunks = 0\nasync for chunk in app.stream_media(message):\n    chunks += 1\nreturn {"chunks": chunks}'
```

## Use a bound Message method

```bash
tgharness python $'m = await app.get_messages("@chat", 123)\nreturn await m.reply("received")'
```

## Register a temporary handler

Handlers require a Python callback and therefore belong in the Python escape hatch. Use the exact handler/filter classes documented by PyroTGFork for the installed version.

For long-running update processing, implement the callback in a real Python module using the programmatic SDK rather than squeezing a large daemon into one CLI snippet.

## Invoke a feature missing from Client

1. Search PyroTGFork Raw API docs.
2. Identify the exact `pyrogram.raw.functions` constructor and its Layer-specific fields.
3. Encode raw types with `$raw_type`.
4. Run `tgharness raw ...`.
5. Inspect `ok`, the returned type, and any RPC error.

## Programmatic SDK

```python
from tgharness.core import tg_session, dispatch

async def task():
    async with tg_session() as app:
        result = await dispatch(
            app,
            "call",
            {
                "method": "get_users",
                "params": {"user_ids": ["me"]},
            },
        )
        return result
```

For direct typed PyroTGFork use:

```python
from tgharness.core import tg_session

async def task():
    async with tg_session() as app:
        return await app.get_me()
```

## Upload a generic file

```bash
tgharness upload @chat ./report.pdf --caption "Report"
```
