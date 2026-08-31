---
name: telegram-harness
description: Operate Telegram through a local PyroTGFork harness.
version: 0.4.1
author: NotMmd
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [telegram, mtproto, pyrotgfork, messaging, automation]
    category: communication
    requires_toolsets: [terminal]
---

# Telegram Harness Skill

Use `tgharness` to let an agent operate a Telegram user session through PyroTGFork. It provides common CLI operations, structured JSON, runtime access to public Client methods, Raw MTProto access, and a Python escape hatch; it does not replace Telegram authorization or platform rules.

## When to Use

Use this skill when the task requires direct Telegram account access, including:

- reading, searching, sending, editing, deleting, forwarding, or copying messages
- uploading, sending, downloading, or streaming Telegram media
- resolving users, chats, dialogs, members, topics, stories, calls, payments, or other PyroTGFork-supported objects
- invoking a public PyroTGFork Client method not exposed as a convenience command
- invoking a Raw Telegram API function through PyroTGFork
- using handlers, filters, callbacks, streams, or bound Telegram objects in a Python workflow
- holding one file-backed Telegram session for repeated agent actions
- installing or repairing the harness or its Agent Skill

## Prerequisites

Use the Hermes `terminal` tool or the equivalent shell tool on another agent runtime.

The library contract is **PyroTGFork only**:

- dependency: `pyrotgfork`
- import namespace: `pyrogram`
- docs: https://telegramplayground.github.io/pyrogram/index.html

Do not use upstream Pyrogram documentation to infer signatures, types, errors, or Raw API behavior. For unfamiliar APIs, inspect the installed Client and consult the PyroTGFork docs above. Read [references/PYROTGFORK.md](references/PYROTGFORK.md) when library-specific detail matters.

Never ask the user to paste these into agent chat:

- API hash
- Telegram confirmation code
- 2FA password
- session string
- `.session` file

For autonomous use, recommend a dedicated Telegram account on a separate number the user controls. A stable virtual number can be acceptable; disposable or recycled numbers are not durable account ownership. A separate account reduces impact on the primary account but does not avoid Telegram anti-spam limits or restrictions.

## How to Run

Check the CLI first:

```bash
command -v tgharness && tgharness --version
```

Install from GitHub without starting an interactive login:

```bash
curl -fsSL https://raw.githubusercontent.com/NotMmd/tgharness/main/bootstrap.sh | bash -s -- --no-setup
```

From a clone, use:

```bash
./install.sh --no-setup
```

For Hermes Agent:

```bash
./install.sh --agent hermes-agent --no-setup
```

For a published repository:

```bash
npx skills add https://github.com/NotMmd/tgharness --skill telegram-harness -g -a hermes-agent -y --copy
```

Hermes installs skills under `~/.hermes/skills/`. Verify with:

```bash
hermes skills list
```

Read [references/INSTALLATION.md](references/INSTALLATION.md) for Codex, Claude Code, Hermes native GitHub installation, and fallback paths.

First-time authorization must be handed to the user in an interactive local terminal:

```bash
tgharness setup
```

If configuration already exists:

```bash
tgharness login
```

The wizard hides the API hash, confirmation code, and 2FA password. If Two-Step Verification is required, it displays Telegram's password hint before asking locally for the password. Read [references/AUTH.md](references/AUTH.md).

## Quick Reference

Use the narrowest surface that fits the task:

```text
convenience command -> call -> raw -> python
```

Common operations:

```bash
tgharness me
tgharness dialogs --limit 20
tgharness history @chat --limit 20
tgharness get-messages 123 --chat @chat
tgharness send @chat "text"
tgharness upload @chat ./file.pdf
tgharness download @chat 123
tgharness edit @chat 123 "new text"
tgharness delete @chat 123
tgharness forward @dest @source 123
tgharness copy @dest @source 123
tgharness search @chat "query" --limit 20
tgharness get-chat @chat
tgharness join @chat
tgharness leave @chat
```

Discover the installed Client:

```bash
tgharness methods [query]
tgharness describe METHOD
```

Call any public Client method:

```bash
tgharness call METHOD --params '{"arg":"value"}'
```

Invoke Raw MTProto:

```bash
tgharness raw namespace.Function --params '{...}'
```

Use async Python only when JSON cannot represent the workflow:

```bash
tgharness python 'await app.get_me()'
```

For repeated operations, keep one session owner:

```bash
tgharness serve
```

Read [references/CLI.md](references/CLI.md) for the full harness command surface and [references/RECIPES.md](references/RECIPES.md) for patterns.

## Procedure

1. Confirm `tgharness --version` works. If not, install the CLI and the skill for the current agent runtime.
2. Confirm authorization with `tgharness me`. If credentials or authorization are missing, hand off `tgharness setup` or `tgharness login` to the user locally.
3. Identify the exact Telegram target before mutating state. Resolve usernames/chats/messages when necessary rather than guessing IDs.
4. Use a convenience command when it exposes the needed operation cleanly.
5. Otherwise run `tgharness methods QUERY` and `tgharness describe METHOD`, then use `tgharness call`.
6. If a Client method requires complex PyroTGFork objects, use tagged JSON values described in [references/JSON_PROTOCOL.md](references/JSON_PROTOCOL.md).
7. If no suitable high-level method exists, consult the PyroTGFork Raw API and use `tgharness raw` with exact Layer-specific constructors.
8. Use `tgharness python` only for callbacks, handlers, filters, streams, bound methods, or multi-step live Python state that cannot be expressed through JSON.
9. For a sequence of operations, start `tgharness serve` so one process owns the file-backed session and CLI requests use IPC.
10. Inspect the returned envelope and verify the target/result before reporting completion.

Normal agent-facing commands return:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

On failure, `ok` is false and `error` contains at least `type` and `message`. Generator calls may set `meta.truncated`; never claim a result set is complete when it is true. Login/setup output is interactive text, not the JSON protocol.

The `python` scope provides `app`, `pyrogram`, `types`, `enums`, `filters`, `handlers`, `raw`, `asyncio`, and `json`. Treat this command as arbitrary local code execution and never interpolate untrusted text into source.

## Pitfalls

- PyroTGFork imports as `pyrogram`; that does not make upstream Pyrogram docs authoritative for this project.
- Do not hand-write a new wrapper merely because a convenience command is missing. `call` discovers public methods on the installed Client at runtime.
- Do not guess Raw constructors. Use the PyroTGFork Raw docs for the installed version.
- Do not run multiple direct clients against the same file-backed session. Prefer the IPC server for repeated work.
- Do not expose session files or authentication secrets in output, logs, prompts, or shell arguments.
- Do not turn FloodWaits or anti-spam errors into aggressive retry loops.
- Be deliberate with destructive actions: deleting histories, leaving/deleting chats, changing permissions, banning members, terminating sessions, changing ownership, and bulk sending.
- Tagged JSON is required for enums, PyroTGFork types, Raw types/functions, bytes, datetimes, and tuples. Read [references/JSON_PROTOCOL.md](references/JSON_PROTOCOL.md).

## Verification

Before reporting success:

1. Require `ok: true` for normal JSON commands.
2. Match returned chat/user/message IDs to the intended target for mutations.
3. Confirm returned file paths for downloads and returned Telegram messages for uploads/sends.
4. Check `meta.truncated` for generator results.
5. State the exact Client or Raw method when reproducibility matters.
6. Confirm `tgharness me` after initial login or session repair.
7. For Hermes installation, confirm `telegram-harness` appears in `hermes skills list`; a newly installed skill may require a new/refresh session before use.
