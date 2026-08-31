# CLI reference

## Setup and login

These commands are interactive and intentionally do not use the JSON envelope:

```bash
tgharness setup
tgharness setup --no-login
tgharness login
```

`setup` writes the user config and, unless `--no-login` is given, launches the login flow. `login` reuses existing configuration. Confirmation codes and 2FA passwords are read without terminal echo; when Two-Step Verification is required, the Telegram password hint is displayed before prompting for the password.

Do not pass API hashes, login codes, or 2FA passwords through agent chat or shell arguments.

All normal commands emit one structured JSON envelope. Global flags must appear before the subcommand.

```text
tgharness [--direct] [--compact] [--request-id ID] COMMAND ...
```

## Transport

```bash
tgharness serve
```

Starts a persistent PyroTGFork session and Unix-domain IPC server. The socket is mode `0600`.

`--direct` bypasses IPC. `--compact` removes pretty JSON indentation. `--request-id` supplies an agent correlation ID echoed in `meta.request_id`.

## Discovery

```bash
tgharness methods [query]
tgharness describe METHOD
```

Use these before unfamiliar calls.

## Universal Client gateway

```bash
tgharness call METHOD --params '{...}' [--collect-limit N]
```

`METHOD` must be a public callable on the active PyroTGFork Client. Arguments are keyword-only from the JSON object after tagged-value decoding.

Generator results are materialized to arrays. `--collect-limit N` overrides the configured cap. `-1` disables the cap.

## Raw API

```bash
tgharness raw FUNCTION --params '{...}' [--retries N] [--timeout SEC] [--sleep-threshold SEC]
```

`FUNCTION` is dotted below `pyrogram.raw.functions`, for example `messages.GetHistory`.

## Python escape hatch

```bash
tgharness python 'CODE'
tgharness exec 'CODE'
```

`exec` is an alias. Single expressions and a single `await ...` return their result automatically. Multi-line snippets should use an explicit `return` when a value must be serialized.

## Convenience commands

### Identity and dialogs

```bash
tgharness me
tgharness dialogs --limit 20
```

### History and message retrieval

```bash
tgharness history CHAT [--limit N] [--min-id N] [--max-id N] [--reverse] [--scheduled]

tgharness get-messages MESSAGE_IDS [--chat CHAT] [--replies N]
```

`MESSAGE_IDS` accepts one integer, comma-separated integers, or a JSON array of integers.

### Send text

```bash
tgharness send CHAT TEXT [--reply-to MESSAGE_ID] [--silent]
```

### Send common media

```bash
tgharness send-media TYPE CHAT FILE [--caption TEXT] [--reply-to MESSAGE_ID]
```

`TYPE` is one of:

- `photo`
- `audio`
- `document`
- `video`
- `animation`
- `voice`
- `video_note`
- `sticker`

Use `call` for the complete send-method surface and parameters not exposed by this convenience command.

### Upload generic file

```bash
tgharness upload @chat ./report.pdf --caption "Report"
```

Options: `--caption`, `--reply-to`, `--silent`. This maps to `send_document()`. For the full parameter surface, use `call send_document`.

### Download

```bash
tgharness download CHAT MESSAGE_ID [--file-name PATH]
```

The harness first resolves the message, then calls PyroTGFork `download_media`. The configured download directory is used when no path is provided.

### Edit/delete

```bash
tgharness edit CHAT MESSAGE_ID TEXT

tgharness delete CHAT MESSAGE_IDS [--local-only] [--scheduled]
```

### Forward/copy

```bash
tgharness forward TO_CHAT FROM_CHAT MESSAGE_IDS [--silent]

tgharness copy TO_CHAT FROM_CHAT MESSAGE_ID
```

### Search

```bash
tgharness search CHAT [QUERY] [--limit N]
```

For filters, sender constraints, dates, topic IDs, and other PyroTGFork search parameters, use `call search_messages --params ...`.

### Chat lookup/membership

```bash
tgharness get-chat CHAT
tgharness join CHAT_OR_INVITE
tgharness leave CHAT [--delete]
```

## Chat identifiers

A CLI chat argument that consists only of digits (optionally prefixed by `-`) is converted to an integer. Other values remain strings, allowing usernames, phone numbers where supported, `me`/`self`, or invite links where the specific PyroTGFork method accepts them.
