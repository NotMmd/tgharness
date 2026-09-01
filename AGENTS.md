# Agent instructions

This repository is `tgharness`, a multi-account Telegram Agent Harness built on PyroTGFork. Canonical repository: https://github.com/NotMmd/tgharness.

## Install

Use the repository installer rather than inventing a custom environment:

```bash
./install.sh --no-setup
```

If you are Hermes Agent:

```bash
./install.sh --agent hermes-agent --no-setup
```

If you are Codex:

```bash
./install.sh --agent codex --no-setup
```

The reusable Agent Skill is `skills/telegram-harness/SKILL.md` and the repo-local Codex discovery path is `.agents/skills/telegram-harness/`.

## Upgrade

For an existing installation, do not re-run authorization just to update code. After pulling a newer checkout, use:

```bash
./install.sh --upgrade
```

From the published repository, use the bootstrap command documented in README. Upgrade mode preserves configuration and Telegram session files, refreshes detected existing skill copies, and skips setup. Restart any long-running `tgharness serve` process afterward.

## Telegram API rule

Use only the PyroTGFork documentation for library behavior:

https://telegramplayground.github.io/pyrogram/index.html

The installed package is `pyrotgfork`; the Python import namespace remains `pyrogram`. Do not use upstream Pyrogram documentation as the contract for this repository.

## Credentials

Do not ask the user to paste API hashes, confirmation codes, 2FA passwords, session strings, or session files into chat. Have the user run authorization locally:

```bash
tgharness setup
tgharness account add NAME --login
tgharness account login NAME
```

The interactive wizard displays the Telegram 2FA hint when needed and accepts secret input without echoing it.

After authorization, inspect accounts with:

```bash
tgharness account list
tgharness account info NAME
```

Use `--account NAME`, `--accounts NAME1,NAME2`, or `--all-accounts` deliberately. Do not assume a command should run from every enabled identity.

For repeated work, prefer `tgharness serve` so one process owns all enabled file-backed sessions.
