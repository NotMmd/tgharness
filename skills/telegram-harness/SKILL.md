---
name: telegram-harness
description: Operate Telegram through a local PyroTGFork harness.
version: 0.5.2
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

Use `tgharness` to let an agent operate one or many Telegram accounts through PyroTGFork. It provides account/session management, common CLI operations, structured JSON, runtime access to public Client methods, Raw MTProto access, and a Python escape hatch; it does not replace Telegram authorization or platform rules.

## When to Use

Use this skill when the task requires direct Telegram account access, including:

- registering, selecting, enabling, disabling, inspecting, or switching between multiple Telegram account sessions
- running the same intentional operation from one named account, selected accounts, or all enabled accounts
- reading, searching, sending, editing, deleting, forwarding, or copying messages
- uploading, sending, downloading, or streaming Telegram media
- retrieving the current account identity, profile details, profile-photo count, or profile photos
- resolving users, chats, dialogs, members, topics, stories, calls, payments, or other PyroTGFork-supported objects
- invoking a public PyroTGFork Client method not exposed as a convenience command
- invoking a Raw Telegram API function through PyroTGFork
- using handlers, filters, callbacks, streams, or bound Telegram objects in a Python workflow
- holding multiple enabled file-backed sessions safely in one long-running harness process
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

Upgrade an existing installation without re-running Telegram setup:

```bash
curl -fsSL https://raw.githubusercontent.com/NotMmd/tgharness/main/bootstrap.sh | bash -s -- --upgrade
```

Upgrade mode preserves existing config/session files and refreshes detected installed copies of this skill. Restart a running `tgharness serve` process afterward.

From a clone:

```bash
./install.sh --no-setup
```

For Hermes Agent:

```bash
./install.sh --agent hermes-agent --no-setup
```

First-time authorization must be handed to the user in an interactive local terminal:

```bash
tgharness setup
```

Add another account with:

```bash
tgharness account add NAME --login
```

Or authorize an already registered account:

```bash
tgharness account login NAME
```

The wizard hides the API hash, confirmation code, and 2FA password. If Two-Step Verification is required, it displays Telegram's password hint before asking locally for the password. Read [references/AUTH.md](references/AUTH.md) and [references/ACCOUNTS.md](references/ACCOUNTS.md).

## Quick Reference

Inspect and manage accounts:

```bash
tgharness account list
tgharness account info NAME
tgharness account info NAME --photos 3
tgharness --all-accounts account info
tgharness account photos NAME --limit 3 --download
tgharness account enable NAME
tgharness account disable NAME
tgharness account default NAME
```

Target Telegram operations explicitly when needed:

```bash
tgharness me
tgharness --account work me
tgharness --accounts default,work send @chat "text"
tgharness --all-accounts dialogs --limit 5
```

Use the narrowest API surface that fits the task:

```text
convenience command -> call -> raw -> python
```

Common operations:

```bash
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

For repeated operations, keep one owner for all enabled sessions:

```bash
tgharness serve
```

Read [references/CLI.md](references/CLI.md) for the full command surface and [references/RECIPES.md](references/RECIPES.md) for patterns.

## Procedure

1. Confirm `tgharness --version` works. If an older installation must be refreshed, use the repository installer with `--upgrade`; otherwise install the CLI and skill for the current agent runtime.
2. Run `tgharness account list` before assuming which identities exist. If no authorized account exists, hand off `tgharness setup` or `tgharness account login NAME` to the user locally.
3. Choose the identity scope deliberately: default, `--account NAME`, `--accounts A,B`, or `--all-accounts`. Never broaden to multiple accounts without task intent.
4. When identity matters, run `tgharness account info NAME`; request/download profile photos only when they materially help the task.
5. Identify the exact Telegram target before mutating state. Resolve usernames/chats/messages rather than guessing IDs.
6. Use a convenience command when it exposes the needed operation cleanly.
7. Otherwise run `tgharness methods QUERY` and `tgharness describe METHOD`, then use `tgharness call`.
8. If a Client method requires complex PyroTGFork objects, use tagged JSON values described in [references/JSON_PROTOCOL.md](references/JSON_PROTOCOL.md).
9. If no suitable high-level method exists, consult the PyroTGFork Raw API and use `tgharness raw` with exact Layer-specific constructors.
10. Use `tgharness python` only for callbacks, handlers, filters, streams, bound methods, or multi-step live Python state that cannot be expressed through JSON.
11. For repeated work, start `tgharness serve` so one process owns every enabled file-backed session and CLI requests use IPC.
12. Inspect the returned envelope, including per-account results for multi-account operations, before reporting completion.

Normal agent-facing commands return:

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {}
}
```

Multi-account requests return `data.results` with one result per account. The top-level `ok` is false if any selected account fails, and `meta.success_count` / `meta.failure_count` summarize the batch.

The `python` scope provides `app`, `pyrogram`, `types`, `enums`, `filters`, `handlers`, `raw`, `asyncio`, and `json`. In a multi-account command, the snippet is executed independently with each selected account's `app`. Treat this command as arbitrary local code execution and never interpolate untrusted text into source.

## Pitfalls

- PyroTGFork imports as `pyrogram`; that does not make upstream Pyrogram docs authoritative for this project.
- A configured account name is a harness selector; its `session_name` is the underlying PyroTGFork session filename. Do not confuse either with a Telegram username.
- Do not open the same file-backed session in multiple direct Client processes at the same time. `tgharness` rejects duplicate account-to-session mappings; prefer `tgharness serve` for repeated work.
- `account disable` is a harness/runtime control; it does not log out of Telegram or revoke the Telegram authorization.
- `account remove --delete-session` deletes local authorization files. Use it only when that is explicitly intended.
- Telegram file IDs are account-bound in many cases. Do not assume media `file_id` values obtained from one account can be reused by another.
- Do not hand-write a new wrapper merely because a convenience command is missing. `call` discovers public methods on the installed Client at runtime.
- Do not guess Raw constructors. Use the PyroTGFork Raw docs for the installed version.
- Do not expose session files or authentication secrets in output, logs, prompts, or shell arguments.
- Do not turn FloodWaits or anti-spam errors into aggressive retry loops.
- Be deliberate with destructive actions and especially with multi-account mutations or bulk sending.

## Verification

Before reporting success:

1. Require `ok: true` for normal JSON commands.
2. For multi-account operations, inspect every `data.results[]` entry and `meta.failure_count`; do not hide partial failures.
3. Match `meta.account`, returned user/chat/message IDs, and the intended identity/target for mutations.
4. Confirm returned file paths before attempting to inspect downloaded profile photos or message media.
5. Check `meta.truncated` for generator results.
6. State the exact Client or Raw method when reproducibility matters.
7. Confirm the intended account with `tgharness account info NAME` after initial login or session repair.
8. For Hermes installation, confirm `telegram-harness` appears in `hermes skills list`; a newly installed skill may require a new/refresh session before use.
