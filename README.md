# tgharness

Telegram MTProto harness for AI agents, powered by **PyroTGFork**.

`tgharness` gives an agent a stable CLI/JSON interface to a Telegram user session while keeping the full PyroTGFork surface reachable through generic Client calls, Raw MTProto, and a Python escape hatch.

> [!IMPORTANT]
> This project uses **PyroTGFork**, installed as `pyrotgfork` and imported through the `pyrogram` Python namespace. API behavior and signatures must be checked against the [PyroTGFork documentation](https://telegramplayground.github.io/pyrogram/index.html), not upstream Pyrogram documentation.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/NotMmd/tgharness/main/bootstrap.sh | bash
tgharness setup
```

Or clone it:

```bash
git clone https://github.com/NotMmd/tgharness.git
cd tgharness
./install.sh
```

The installer prefers `uv tool`, then `pipx`, and falls back to an isolated user venv. It can also install the bundled Agent Skill.

### Hermes Agent

```bash
curl -fsSL https://raw.githubusercontent.com/NotMmd/tgharness/main/bootstrap.sh | bash -s -- --agent hermes-agent --no-setup
tgharness setup
```

Or install only the skill:

```bash
npx skills add https://github.com/NotMmd/tgharness --skill telegram-harness -g -a hermes-agent -y --copy
```

Hermes also supports installing a skill directly from a public GitHub repository path:

```bash
hermes skills install NotMmd/tgharness/skills/telegram-harness
```

### Codex / other Agent Skills clients

```bash
npx skills add https://github.com/NotMmd/tgharness --skill telegram-harness -g -a codex -y --copy
```

The repository also exposes the skill at `.agents/skills/telegram-harness/` for repo-local Codex discovery.

## Setup and login

Get an API ID and API hash from [my.telegram.org/apps](https://my.telegram.org/apps), then run:

```bash
tgharness setup
```

The setup flow stores configuration in `~/.config/tgharness/config.yaml` by default and immediately opens the login wizard:

```text
tgharness setup

API ID: 12345678
API hash: [hidden]
✓ Config saved

Telegram login
Phone [+]: +41...
Code sent: APP · resend in 60s
Login code: [hidden]
Two-Step Verification required
Hint: your Telegram 2FA hint
2FA password: [hidden]
✓ Logged in as Example User (@example) · 123456789
```

The API hash, login code, and 2FA password are hidden while typing. If configuration already exists, use:

```bash
tgharness login
```

For an autonomous agent, prefer a **separate Telegram account** on a secondary SIM/number you control instead of your primary account. A reputable long-lived virtual number can also be used, but disposable or recycled numbers are a poor choice because access can be lost or reassigned. Telegram may restrict accounts that behave like spam or abusive automation, so isolating agent activity reduces the blast radius; it does not make automation risk-free.

## Give this to your agent

Paste this into the agent:

```text
Install tgharness from https://github.com/NotMmd/tgharness and install its `telegram-harness` Agent Skill for yourself. You may use `curl -fsSL https://raw.githubusercontent.com/NotMmd/tgharness/main/bootstrap.sh | bash -s -- --no-setup` to bootstrap the CLI. If you are Hermes Agent, install the skill for Hermes and verify it appears in `hermes skills list`. If you are Codex or another Agent Skills client, use the native/global skill location for that agent.

This project uses PyroTGFork, not upstream Pyrogram. For Telegram library APIs, signatures, types, errors, and Raw MTProto, use only https://telegramplayground.github.io/pyrogram/index.html.

Install the tgharness CLI, verify `tgharness --version`, then help me configure it. Do not ask me to paste my Telegram API hash, login code, 2FA password, session string, or session file into chat. When secrets or Telegram authorization are needed, ask me to run `tgharness setup` or `tgharness login` locally in an interactive terminal. The login wizard shows the Telegram 2FA hint and accepts the password locally without echoing it.

After login, verify the account with `tgharness me`. Use `tgharness methods` and `tgharness describe <method>` before unfamiliar Client calls. Prefer convenience commands for common work, `tgharness call` for any public PyroTGFork Client method, `tgharness raw` when Raw MTProto is needed, and `tgharness python` only when callbacks, handlers, streams, or live Python objects cannot be represented through JSON. For repeated commands, use `tgharness serve` so the session is held by one process.
```

## Use

```bash
tgharness me
tgharness dialogs --limit 20
tgharness history @username --limit 20
tgharness send @username "hello"
tgharness upload @username ./file.pdf
tgharness download @username 12345
```

Discover and call the installed PyroTGFork Client at runtime:

```bash
tgharness methods stories
tgharness describe get_stories
tgharness call get_chat --params '{"chat_id":"@username"}'
```

Raw MTProto remains available when the high-level Client API is not enough:

```bash
tgharness raw messages.GetHistory --params '{"peer":{"$raw_type":"InputPeerSelf","kwargs":{}},"offset_id":0,"offset_date":0,"add_offset":0,"limit":10,"max_id":0,"min_id":0,"hash":0}'
```

For long-running agent sessions:

```bash
tgharness serve
```

Normal agent-facing operations return structured JSON using a stable `ok / data / error / meta` envelope.

## Configuration

Default paths:

- config: `~/.config/tgharness/config.yaml`
- session/data: `~/.local/share/tgharness/`
- IPC socket: `$XDG_RUNTIME_DIR/tgharness-<uid>.sock` or `/tmp/tgharness-<uid>.sock`

Environment overrides use the `TGHARNESS_*` prefix. See `config.example.yaml` and the bundled skill references for details.

## Agent Skill

The canonical distributable skill is under:

```text
skills/telegram-harness/
```

It follows the Agent Skills layout and includes Hermes metadata plus OpenAI/Codex `agents/openai.yaml` metadata. Detailed CLI, JSON protocol, PyroTGFork, authentication, installation, and recipe notes live under `references/` so the main `SKILL.md` stays small.

## Development

```bash
python -m unittest discover -s tests -v
python -m compileall -q tgharness
```

## Credits

Vibe-coded with **GPT-5.6 Sol** and **Gemini 3.7 Flash**.

## License

MIT
