import getpass
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from pyrogram.errors import SessionPasswordNeeded

from .client import get_client
from .config import Config, DATA_HOME, DEFAULT_CONFIG_PATH


def _style(text: str, code: str) -> str:
    if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
        return text
    return f"\033[{code}m{text}\033[0m"


def _title(text: str) -> None:
    print()
    print(_style(text, "1;36"))
    print(_style("─" * len(text), "2"))


def _ok(text: str) -> None:
    print(_style(f"✓ {text}", "1;32"))


def _prompt(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or (default or "")


def _secret(label: str) -> str:
    return getpass.getpass(f"{label}: ").strip()


def write_config(
    *,
    api_id: int,
    api_hash: str,
    session_name: str = "tgharness",
    workdir: str | Path | None = None,
    config_path: str | Path | None = None,
) -> Path:
    path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    data_dir = Path(workdir).expanduser() if workdir else DATA_HOME
    payload = {
        "telegram": {
            "api_id": int(api_id),
            "api_hash": api_hash,
            "session_name": session_name,
            "workdir": str(data_dir),
            "bot_token": None,
            "proxy": None,
            "in_memory": False,
            "no_updates": False,
            "sleep_threshold": 10,
        },
        "harness": {
            "ipc_socket": None,
            "ipc_timeout": 60,
            "collect_limit": 100,
            "download_dir": None,
            "pretty_json": True,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
    os.chmod(path, 0o600)
    return path


def setup_interactive(
    *,
    api_id: int | None = None,
    api_hash: str | None = None,
    session_name: str | None = None,
    workdir: str | Path | None = None,
    config_path: str | Path | None = None,
) -> Config:
    path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
    current = Config(path)
    _title("tgharness setup")
    print("Get API credentials from https://my.telegram.org/apps")

    if api_id is not None:
        chosen_api_id = api_id
    else:
        raw_api_id = _prompt("API ID", str(current.api_id) if current.api_id else None)
        if not raw_api_id.isdigit():
            raise ValueError("API ID must be an integer")
        chosen_api_id = int(raw_api_id)

    if api_hash is not None:
        chosen_api_hash = api_hash
    elif current.api_hash:
        entered_hash = getpass.getpass("API hash [press Enter to keep current]: ").strip()
        chosen_api_hash = entered_hash or current.api_hash
    else:
        chosen_api_hash = _secret("API hash")
    if not chosen_api_hash:
        raise ValueError("API hash is required")

    chosen_session = session_name or current.session_name or "tgharness"
    chosen_workdir = Path(workdir).expanduser() if workdir else current.workdir
    saved = write_config(
        api_id=int(chosen_api_id),
        api_hash=str(chosen_api_hash),
        session_name=chosen_session,
        workdir=chosen_workdir,
        config_path=path,
    )
    _ok(f"Config saved to {saved}")
    print(f"Session data: {chosen_workdir}")
    return Config(saved)


def _sent_code_label(sent: Any) -> str:
    value = getattr(sent, "type", None)
    if value is None:
        return "Telegram"
    name = getattr(value, "name", None)
    return str(name or value).replace("SentCodeType.", "")


def _display_user(user: Any) -> str:
    first = getattr(user, "first_name", None) or ""
    last = getattr(user, "last_name", None) or ""
    username = getattr(user, "username", None)
    user_id = getattr(user, "id", None)
    name = " ".join(part for part in (first, last) if part).strip()
    identity = name or (f"@{username}" if username else "Telegram account")
    if username and name:
        identity += f" (@{username})"
    if user_id is not None:
        identity += f" · {user_id}"
    return identity


async def login_interactive(*, cfg: Config | None = None, phone: str | None = None) -> Any:
    active = cfg or Config()
    if not sys.stdin.isatty():
        raise RuntimeError("Interactive login needs a TTY. Run `tgharness login` in your terminal.")
    app = get_client(cfg=active)
    connected = False
    _title("Telegram login")
    try:
        authorized = await app.connect()
        connected = True
        if authorized:
            user = await app.get_me()
            _ok(f"Already logged in as {_display_user(user)}")
            return user

        chosen_phone = phone or _prompt("Phone", "+")
        sent = await app.send_code(chosen_phone)
        delivery = _sent_code_label(sent)
        timeout = getattr(sent, "timeout", None)
        timeout_text = f" · resend in {timeout}s" if timeout else ""
        print(f"Code sent: {delivery}{timeout_text}")
        code = getpass.getpass("Login code: ").strip().replace(" ", "").replace("-", "")
        if not code:
            raise ValueError("Login code is required")

        try:
            user = await app.sign_in(chosen_phone, sent.phone_code_hash, code)
        except SessionPasswordNeeded:
            hint = await app.get_password_hint()
            print(_style("Two-Step Verification required", "1;33"))
            print(f"Hint: {hint or '—'}")
            password = getpass.getpass("2FA password: ")
            if not password:
                raise ValueError("2FA password is required")
            user = await app.check_password(password)

        if user is False or type(user).__name__ == "TermsOfService":
            raise RuntimeError("This number is not ready for user authorization. Create/finish the account in an official Telegram app first.")

        _ok(f"Logged in as {_display_user(user)}")
        print(f"Session: {active.session_path}.session")
        return user
    finally:
        if connected:
            await app.disconnect()
