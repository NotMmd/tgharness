# Agent instructions

This repository is `tgharness`, a Telegram Agent Harness built on PyroTGFork. Canonical repository: https://github.com/NotMmd/tgharness.

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

## Telegram API rule

Use only the PyroTGFork documentation for library behavior:

https://telegramplayground.github.io/pyrogram/index.html

The installed package is `pyrotgfork`; the Python import namespace remains `pyrogram`. Do not use upstream Pyrogram documentation as the contract for this repository.

## Credentials

Do not ask the user to paste API hashes, confirmation codes, 2FA passwords, session strings, or session files into chat. Have the user run this locally:

```bash
tgharness setup
```

Use `tgharness login` if configuration already exists. The interactive wizard displays the Telegram 2FA hint when needed and accepts secret input without echoing it.

After authorization, verify with:

```bash
tgharness me
```

For repeated work, prefer `tgharness serve` before issuing many agent commands.
