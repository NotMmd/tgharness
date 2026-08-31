import os
from pathlib import Path
from typing import Any

import yaml


def _xdg_dir(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name)
    return Path(value).expanduser() if value else fallback


CONFIG_HOME = _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / "tgharness"
DATA_HOME = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / "tgharness"
DEFAULT_CONFIG_PATH = Path(os.environ.get("TGHARNESS_CONFIG", CONFIG_HOME / "config.yaml")).expanduser()


def _env(name: str, default: Any = None) -> Any:
    value = os.environ.get(name)
    return default if value is None else value


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    def __init__(self, config_path: str | Path | None = None):
        self.config_path = Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH
        self._raw = self._load()

        telegram = self._raw.get("telegram", {})
        self.api_id = int(_env("TGHARNESS_API_ID", telegram.get("api_id") or 0)) or None
        self.api_hash = _env("TGHARNESS_API_HASH", telegram.get("api_hash"))
        self.bot_token = _env("TGHARNESS_BOT_TOKEN", telegram.get("bot_token"))
        self.session_name = str(_env("TGHARNESS_SESSION", telegram.get("session_name", "tgharness")))
        self.workdir = Path(_env("TGHARNESS_WORKDIR", telegram.get("workdir") or DATA_HOME)).expanduser().resolve()
        self.session_path = str(self.workdir / self.session_name)
        self.proxy = telegram.get("proxy") or None
        self.in_memory = _as_bool(_env("TGHARNESS_IN_MEMORY", telegram.get("in_memory")), False)
        self.no_updates = _as_bool(_env("TGHARNESS_NO_UPDATES", telegram.get("no_updates")), False)
        self.sleep_threshold = int(_env("TGHARNESS_SLEEP_THRESHOLD", telegram.get("sleep_threshold", 10)))

        harness = self._raw.get("harness", {})
        default_socket = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / f"tgharness-{os.getuid()}.sock"
        ipc_socket = _env("TGHARNESS_IPC_SOCKET", harness.get("ipc_socket") or default_socket)
        self.ipc_socket = Path(ipc_socket).expanduser()
        self.ipc_timeout = float(_env("TGHARNESS_IPC_TIMEOUT", harness.get("ipc_timeout", 60)))
        self.collect_limit = int(_env("TGHARNESS_COLLECT_LIMIT", harness.get("collect_limit", 100)))
        self.download_dir = Path(
            _env("TGHARNESS_DOWNLOAD_DIR", harness.get("download_dir") or self.workdir / "downloads")
        ).expanduser().resolve()
        self.pretty_json = _as_bool(_env("TGHARNESS_PRETTY_JSON", harness.get("pretty_json")), True)

    def _load(self) -> dict:
        if not self.config_path.exists():
            return {}
        with self.config_path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Configuration root must be a mapping: {self.config_path}")
        return data

    def validate(self) -> None:
        if not self.api_id or not self.api_hash:
            raise RuntimeError("Telegram api_id/api_hash are required. Run `tgharness setup` first.")
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)


config = Config()
