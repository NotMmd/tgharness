# CLI reference

## Global syntax

Normal commands emit a structured JSON envelope. Global flags must appear before the subcommand:

```text
tgharness [--direct] [--compact] [--request-id ID]
          [--account NAME | --accounts A,B | --all-accounts]
          COMMAND ...
```

Account targeting applies to Telegram operations. Without a selector, the configured default account is used.

## Setup and login

These commands are interactive and intentionally do not use the JSON envelope:

```bash
tgharness setup
tgharness setup --no-login
tgharness login --account NAME
tgharness account login NAME
```

`setup` writes shared Telegram API configuration and creates the initial account registry if needed. Confirmation codes and 2FA passwords are read without terminal echo; when Two-Step Verification is required, Telegram's password hint is displayed before prompting for the password.

Do not pass API hashes, login codes, 2FA passwords, session strings, or session files through agent chat.

## Account/session management

```bash
tgharness account list
tgharness account add NAME [--session SESSION] [--disabled] [--default] [--login]
tgharness account login [NAME]
tgharness account enable NAME
tgharness account disable NAME
tgharness account default NAME
tgharness account remove NAME [--delete-session]
tgharness account info [NAME] [--photos N] [--download-photos]
tgharness account photos [NAME] [--limit N] [--download]
```

`account remove` keeps the session file by default. `--delete-session` explicitly deletes local session/journal files.

## Transport

```bash
tgharness serve
```

Starts one Unix-domain IPC server and owns one live PyroTGFork Client per enabled authorized account. The socket is mode `0600`.

`--direct` bypasses IPC. `--compact` removes pretty JSON indentation. `--request-id` supplies an agent correlation ID echoed in `meta.request_id`.

## Account selectors

```bash
tgharness --account work me
tgharness --accounts default,work send @chat "hello"
tgharness --all-accounts dialogs --limit 5
```

Multi-account operations return `data.results` and batch success/failure counts. Do not treat a partially successful batch as fully successful.

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

`METHOD` must be a public callable on the selected PyroTGFork Client. Arguments are keyword-only from the JSON object after tagged-value decoding.

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

`exec` is an alias. Single expressions and a single `await ...` return their result automatically. Multi-line snippets should use an explicit `return` when a value must be serialized. With multiple account selectors, the snippet runs independently against each account's `app`.

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

`TYPE` is one of `photo`, `audio`, `document`, `video`, `animation`, `voice`, `video_note`, or `sticker`. Use `call` for the complete send-method surface and parameters not exposed by this convenience command.

### Upload / download

```bash
tgharness upload @chat ./report.pdf --caption "Report"
tgharness download CHAT MESSAGE_ID [--file-name PATH]
```

### Edit / delete

```bash
tgharness edit CHAT MESSAGE_ID TEXT
tgharness delete CHAT MESSAGE_IDS [--local-only] [--scheduled]
```

### Forward / copy

```bash
tgharness forward TO_CHAT FROM_CHAT MESSAGE_IDS [--silent]
tgharness copy TO_CHAT FROM_CHAT MESSAGE_ID
```

### Search / chat membership

```bash
tgharness search CHAT [QUERY] [--limit N]
tgharness get-chat CHAT
tgharness join CHAT_OR_INVITE
tgharness leave CHAT [--delete]
```

## Chat identifiers

A CLI chat argument that consists only of digits (optionally prefixed by `-`) is converted to an integer. Other values remain strings, allowing usernames, phone numbers where supported, `me`/`self`, or invite links where the specific PyroTGFork method accepts them.
