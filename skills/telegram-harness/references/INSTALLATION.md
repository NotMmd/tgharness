# Installation

## Repository installer

From a checkout:

```bash
./install.sh
```

The installer uses, in order:

1. `uv tool install --force <repo>`
2. `pipx install --force <repo>`
3. an isolated venv under `${XDG_DATA_HOME:-~/.local/share}/tgharness/venv`

Use `--no-setup` when an agent is performing the package installation and the human will authorize later.

## Remote bootstrap

```bash
curl -fsSL https://raw.githubusercontent.com/NotMmd/tgharness/main/bootstrap.sh | bash -s -- --no-setup
```

## Upgrade an existing installation

When an agent is asked to perform the upgrade, it should treat the existing configuration and Telegram sessions as persistent user state: use `--upgrade`, refresh its installed skill copy, avoid re-running authorization, restart a running `tgharness serve`, then verify `tgharness --version` and `tgharness account list`. The README contains a copy/paste upgrade prompt for users.


Once the newer repository version is on `main`:

```bash
curl -fsSL https://raw.githubusercontent.com/NotMmd/tgharness/main/bootstrap.sh | bash -s -- --upgrade
```

Upgrade mode force-reinstalls the current package from the fetched checkout, skips interactive Telegram setup, preserves the user's config and `.session` files, and refreshes detected existing `telegram-harness` skill copies. It also detects Hermes, Codex, and Claude Code runtimes on PATH.

For a pre-0.5 installation, the old single-session config is intentionally accepted as the `default` account. Do not delete or rename the old session as part of an upgrade. Verify with:

```bash
tgharness --version
tgharness account list
```

If `tgharness serve` is already running, restart that long-running process after the package update.

If the skill was installed through an update-aware manager rather than this installer, its native update flow can also be used. Current Skills CLI supports `npx skills update telegram-harness -g -y`; current Hermes skill installs can be checked/updated with `hermes skills check` and `hermes skills update`.

## Hermes Agent

```bash
./install.sh --agent hermes-agent --no-setup
```

From a published Git repository:

```bash
npx skills add https://github.com/NotMmd/tgharness --skill telegram-harness -g -a hermes-agent -y --copy
```

Hermes native location:

```text
~/.hermes/skills/telegram-harness/
```

Hermes can also install a public GitHub skill path directly:

```bash
hermes skills install NotMmd/tgharness/skills/telegram-harness
```

Verify:

```bash
hermes skills list
```

If the skill was installed during an already-running Hermes session and is not visible yet, start a new session or use Hermes' current skill refresh/reset mechanism.

## Codex

```bash
npx skills add https://github.com/NotMmd/tgharness --skill telegram-harness -g -a codex -y --copy
```

The repository also includes `.agents/skills/telegram-harness/` for repo-local discovery.

## Claude Code

```bash
npx skills add https://github.com/NotMmd/tgharness --skill telegram-harness -g -a claude-code -y --copy
```

## Agent-led installation

An agent may install the CLI and Skill, verify binaries, and inspect non-secret configuration. It must hand off interactive authorization to the user rather than requesting login codes, API hashes, 2FA passwords, session strings, or session files in chat.

Recommended sequence:

```text
install package -> install skill -> verify tgharness --version -> ask user to run tgharness setup -> inspect tgharness account list -> verify tgharness account info default -> optionally add more accounts -> optionally start tgharness serve
```
