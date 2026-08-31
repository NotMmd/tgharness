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
install package -> install skill -> verify tgharness --version -> ask user to run tgharness setup -> verify tgharness me -> optionally start tgharness serve
```
