# Multi-account sessions

`tgharness` keeps a registry of named accounts. Each account name maps to its own PyroTGFork session filename, so the agent can select identities without handling session files directly.

## Register and authorize

```bash
tgharness account add work --login
```

Or separate registration from authorization:

```bash
tgharness account add work --disabled
tgharness account login work
tgharness account enable work
```

`account login` is interactive and must be run by the user locally when Telegram asks for secrets.

## Inspect state

```bash
tgharness account list
```

The result exposes non-secret registry/runtime fields such as account name, underlying session name, whether it is enabled, whether its session file exists, whether it is the default, and whether the long-running server currently owns it.

## Target commands

Default account:

```bash
tgharness me
```

One named account:

```bash
tgharness --account work me
```

Selected accounts:

```bash
tgharness --accounts default,work send @chat "hello"
```

All enabled accounts:

```bash
tgharness --all-accounts me
```

Do not expand a single-account task to multiple accounts unless the user's intent requires it.

## Enable and disable

```bash
tgharness account disable work
tgharness account enable work
```

Disabled accounts cannot be selected for Telegram operations. With `tgharness serve` running, disabling stops its live Client and enabling starts the authorized Client. Disabling does not log out of Telegram or delete the session.

## Default account

```bash
tgharness account default work
```

A disabled account cannot be made the default.

## Identity and profile inspection

```bash
tgharness account info work
```

This returns:

- non-secret harness account/session metadata
- the full JSON-serialized `User` from PyroTGFork `get_me()`
- a fuller chat/profile object when `get_chat("me")` succeeds
- `profile_photo_count` from `get_chat_photos_count("me")`

Request photo metadata only when needed:

```bash
tgharness account info work --photos 5
```

Inspect multiple enabled identities in one call:

```bash
tgharness --accounts default,work account info
tgharness --all-accounts account info
```

Download profile photos for local vision inspection:

```bash
tgharness account photos work --limit 5 --download
tgharness --accounts default,work account photos --limit 2 --download
```

The JSON returns local file paths. A vision-capable agent may open those files with its local image/file tool. Photos are not downloaded by default. Each configured account must map to a distinct session file; duplicate mappings are rejected.

## Remove an account

Registry only:

```bash
tgharness account remove work
```

Registry plus local PyroTGFork session files:

```bash
tgharness account remove work --delete-session
```

The latter is destructive to local authorization state. It does not delete the Telegram account itself.

## Multi-account JSON

A multi-account operation returns one child result per account under `data.results`. Each child keeps its own `ok`, `data`, `error`, and `meta.account`. The parent `meta` contains success/failure counts. Treat any nonzero `failure_count` as a partial failure that must be surfaced.
