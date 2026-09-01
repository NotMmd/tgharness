import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def _xdg_dir(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name)
    return Path(value).expanduser() if value else fallback


CONFIG_HOME = _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / "tgharness"
DATA_HOME = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / "tgharness"
DEFAULT_CONFIG_PATH = Path(os.environ.get("TGHARNESS_CONFIG", CONFIG_HOME / "config.yaml")).expanduser()
_ACCOUNT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _env(name: str, default: Any = None) -> Any:
    value = os.environ.get(name)
    return default if value is None else value


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def validate_account_name(name: str) -> str:
    value = str(name).strip()
    if not _ACCOUNT_NAME_RE.fullmatch(value):
        raise ValueError("Account name must be 1-64 chars using letters, numbers, '.', '_' or '-'.")
    return value


@dataclass(frozen=True)
class AccountConfig:
    name: str
    session_name: str
    enabled: bool
    workdir: Path
    bot_token: str | None
    proxy: dict | None
    in_memory: bool
    no_updates: bool
    sleep_threshold: int

    @property
    def session_path(self) -> Path:
        return self.workdir / self.session_name

    @property
    def session_file(self) -> Path:
        return Path(str(self.session_path) + ".session")

    def public_dict(self, *, default: bool = False) -> dict[str, Any]:
        return {
            "name": self.name,
            "session_name": self.session_name,
            "enabled": self.enabled,
            "default": default,
            "session_file": str(self.session_file),
            "session_exists": self.session_file.exists(),
            "in_memory": self.in_memory,
            "no_updates": self.no_updates,
        }


class Config:
    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
        self._raw = self._load()
        self._read_values()

    def _read_values(self) -> None:
        telegram = self._raw.get("telegram", {})
        if not isinstance(telegram, dict):
            raise ValueError("telegram configuration must be a mapping")

        self.api_id = int(_env("TGHARNESS_API_ID", telegram.get("api_id") or 0)) or None
        self.api_hash = _env("TGHARNESS_API_HASH", telegram.get("api_hash"))
        self.workdir = Path(_env("TGHARNESS_WORKDIR", telegram.get("workdir") or DATA_HOME)).expanduser().resolve()
        self.proxy = telegram.get("proxy") or None
        self.in_memory = _as_bool(_env("TGHARNESS_IN_MEMORY", telegram.get("in_memory")), False)
        self.no_updates = _as_bool(_env("TGHARNESS_NO_UPDATES", telegram.get("no_updates")), False)
        self.sleep_threshold = int(_env("TGHARNESS_SLEEP_THRESHOLD", telegram.get("sleep_threshold", 10)))
        self.bot_token = _env("TGHARNESS_BOT_TOKEN", telegram.get("bot_token"))

        legacy_session = str(_env("TGHARNESS_SESSION", telegram.get("session_name", "tgharness")))
        configured_default = str(_env("TGHARNESS_ACCOUNT", telegram.get("default_account") or "default"))
        try:
            configured_default = validate_account_name(configured_default)
        except ValueError:
            configured_default = "default"

        raw_accounts = telegram.get("accounts")
        accounts: dict[str, dict[str, Any]] = {}
        if isinstance(raw_accounts, dict):
            for raw_name, raw_entry in raw_accounts.items():
                name = validate_account_name(str(raw_name))
                entry = raw_entry if isinstance(raw_entry, dict) else {}
                accounts[name] = dict(entry)

        # Backward compatibility with the pre-0.5 single-session config.
        if not accounts:
            accounts[configured_default] = {
                "session_name": legacy_session,
                "enabled": True,
            }

        if configured_default not in accounts:
            configured_default = next(iter(accounts))

        self.accounts = accounts
        self.default_account = configured_default
        self._validate_unique_sessions()
        default_cfg = self.account(self.default_account, allow_disabled=True)
        self.session_name = default_cfg.session_name
        self.session_path = str(default_cfg.session_path)

        harness = self._raw.get("harness", {})
        if not isinstance(harness, dict):
            raise ValueError("harness configuration must be a mapping")
        default_socket = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / f"tgharness-{os.getuid()}.sock"
        ipc_socket = _env("TGHARNESS_IPC_SOCKET", harness.get("ipc_socket") or default_socket)
        self.ipc_socket = Path(ipc_socket).expanduser()
        self.ipc_timeout = float(_env("TGHARNESS_IPC_TIMEOUT", harness.get("ipc_timeout", 60)))
        self.collect_limit = int(_env("TGHARNESS_COLLECT_LIMIT", harness.get("collect_limit", 100)))
        self.download_dir = Path(
            _env("TGHARNESS_DOWNLOAD_DIR", harness.get("download_dir") or self.workdir / "downloads")
        ).expanduser().resolve()
        self.pretty_json = _as_bool(_env("TGHARNESS_PRETTY_JSON", harness.get("pretty_json")), True)

    def _validate_unique_sessions(self) -> None:
        seen: dict[Path, str] = {}
        for name, raw in self.accounts.items():
            session_name = str(raw.get("session_name") or name).strip()
            if not session_name or "/" in session_name or "\\" in session_name:
                raise ValueError(
                    f"Account '{name}' has an invalid session_name; use a plain file name without path separators"
                )
            workdir = Path(raw.get("workdir") or self.workdir).expanduser().resolve()
            session_file = Path(str(workdir / session_name) + ".session")
            previous = seen.get(session_file)
            if previous is not None:
                raise ValueError(
                    f"Accounts '{previous}' and '{name}' resolve to the same session file. "
                    "Each tgharness account must use a distinct session."
                )
            seen[session_file] = name

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {}
        with self.config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Configuration root must be a mapping: {self.config_path}")
        return data

    def save(self) -> Path:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.workdir.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(self._raw, handle, sort_keys=False, allow_unicode=True)
        os.chmod(self.config_path, 0o600)
        self._read_values()
        return self.config_path

    def validate_credentials(self) -> None:
        if not self.api_id or not self.api_hash:
            raise RuntimeError("Telegram api_id/api_hash are required. Run `tgharness setup` first.")
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def validate(self) -> None:
        self.validate_credentials()
        self.account(self.default_account)

    def account_names(self, *, enabled_only: bool = False) -> list[str]:
        names = list(self.accounts)
        if enabled_only:
            names = [name for name in names if self.account(name, allow_disabled=True).enabled]
        return names

    def account(self, name: str | None = None, *, allow_disabled: bool = False) -> AccountConfig:
        selected = validate_account_name(name or self.default_account)
        if selected not in self.accounts:
            raise KeyError(f"Unknown tgharness account: {selected}")
        raw = self.accounts[selected]
        session_name = str(raw.get("session_name") or selected)
        enabled = _as_bool(raw.get("enabled"), True)
        if not enabled and not allow_disabled:
            raise RuntimeError(f"Account '{selected}' is disabled. Enable it with `tgharness account enable {selected}`.")
        workdir = Path(raw.get("workdir") or self.workdir).expanduser().resolve()
        return AccountConfig(
            name=selected,
            session_name=session_name,
            enabled=enabled,
            workdir=workdir,
            bot_token=raw.get("bot_token", self.bot_token) or None,
            proxy=raw.get("proxy", self.proxy) or None,
            in_memory=_as_bool(raw.get("in_memory"), self.in_memory),
            no_updates=_as_bool(raw.get("no_updates"), self.no_updates),
            sleep_threshold=int(raw.get("sleep_threshold", self.sleep_threshold)),
        )


    def _materialize_accounts(self) -> dict[str, Any]:
        telegram = self._raw.setdefault("telegram", {})
        raw_accounts = telegram.get("accounts")
        if not isinstance(raw_accounts, dict):
            raw_accounts = {}
            telegram["accounts"] = raw_accounts
        if not raw_accounts:
            for name in self.account_names():
                account_cfg = self.account(name, allow_disabled=True)
                raw_accounts[name] = {
                    "session_name": account_cfg.session_name,
                    "enabled": account_cfg.enabled,
                }
            telegram.setdefault("default_account", self.default_account)
        return raw_accounts

    def public_accounts(self) -> list[dict[str, Any]]:
        return [
            self.account(name, allow_disabled=True).public_dict(default=name == self.default_account)
            for name in self.account_names()
        ]

    def add_account(
        self,
        name: str,
        *,
        session_name: str | None = None,
        enabled: bool = True,
        make_default: bool = False,
    ) -> AccountConfig:
        account_name = validate_account_name(name)
        if account_name in self.accounts:
            raise ValueError(f"Account '{account_name}' already exists")
        if make_default and not enabled:
            raise ValueError("A disabled account cannot be made the default")
        chosen_session = str(session_name or account_name).strip()
        if not chosen_session or "/" in chosen_session or "\\" in chosen_session:
            raise ValueError("Session name must be a plain file name without path separators")
        candidate_file = Path(str(self.workdir / chosen_session) + ".session")
        for existing_name in self.account_names():
            existing = self.account(existing_name, allow_disabled=True)
            if existing.session_file == candidate_file:
                raise ValueError(
                    f"Session '{chosen_session}' is already assigned to account '{existing_name}'. "
                    "Each tgharness account must use a distinct session."
                )
        telegram = self._raw.setdefault("telegram", {})
        raw_accounts = self._materialize_accounts()
        raw_accounts[account_name] = {"session_name": chosen_session, "enabled": bool(enabled)}
        if make_default or not telegram.get("default_account"):
            telegram["default_account"] = account_name
        self.save()
        return self.account(account_name, allow_disabled=True)

    def set_account_enabled(self, name: str, enabled: bool) -> AccountConfig:
        account_name = validate_account_name(name)
        if account_name not in self.accounts:
            raise KeyError(f"Unknown tgharness account: {account_name}")
        self._raw.setdefault("telegram", {})
        raw_accounts = self._materialize_accounts()
        raw_accounts[account_name]["enabled"] = bool(enabled)
        self.save()
        return self.account(account_name, allow_disabled=True)

    def set_default_account(self, name: str) -> AccountConfig:
        account_name = validate_account_name(name)
        if account_name not in self.accounts:
            raise KeyError(f"Unknown tgharness account: {account_name}")
        account_cfg = self.account(account_name, allow_disabled=True)
        if not account_cfg.enabled:
            raise ValueError(f"Cannot make disabled account '{account_name}' the default")
        self._raw.setdefault("telegram", {})["default_account"] = account_name
        self.save()
        return self.account(account_name, allow_disabled=True)

    def remove_account(self, name: str) -> AccountConfig:
        account_name = validate_account_name(name)
        if account_name not in self.accounts:
            raise KeyError(f"Unknown tgharness account: {account_name}")
        if len(self.accounts) <= 1:
            raise ValueError("Cannot remove the last configured account")
        removed = self.account(account_name, allow_disabled=True)
        telegram = self._raw.setdefault("telegram", {})
        raw_accounts = self._materialize_accounts()
        raw_accounts.pop(account_name, None)
        if telegram.get("default_account") == account_name:
            telegram["default_account"] = next(iter(raw_accounts))
        self.save()
        return removed


config = Config()
