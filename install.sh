#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENTS=()
RUN_SETUP=1
UPGRADE=0

usage() {
  printf '%s\n' "Usage: ./install.sh [--agent NAME]... [--no-setup] [--upgrade]"
  printf '%s\n' "Examples:"
  printf '%s\n' "  ./install.sh"
  printf '%s\n' "  ./install.sh --agent hermes-agent"
  printf '%s\n' "  ./install.sh --agent hermes-agent --agent codex --no-setup"
  printf '%s\n' "  ./install.sh --upgrade"
}

add_agent() {
  local candidate="$1"
  local existing
  for existing in "${AGENTS[@]}"; do
    [[ "$existing" == "$candidate" ]] && return 0
  done
  AGENTS+=("$candidate")
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      [[ $# -ge 2 ]] || { echo "--agent requires a value" >&2; exit 2; }
      add_agent "$2"
      shift 2
      ;;
    --no-setup)
      RUN_SETUP=0
      shift
      ;;
    --upgrade)
      UPGRADE=1
      RUN_SETUP=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

install_cli() {
  if command -v uv >/dev/null 2>&1; then
    uv tool install --force "$ROOT"
    return
  fi
  if command -v pipx >/dev/null 2>&1; then
    pipx install --force "$ROOT"
    return
  fi

  local data_home="${XDG_DATA_HOME:-$HOME/.local/share}/tgharness"
  local bin_home="${XDG_BIN_HOME:-$HOME/.local/bin}"
  local venv="$data_home/venv"
  python3 -m venv "$venv"
  "$venv/bin/python" -m pip install --upgrade pip
  "$venv/bin/pip" install --upgrade "$ROOT"
  mkdir -p "$bin_home"
  ln -sfn "$venv/bin/tgharness" "$bin_home/tgharness"
  printf 'Installed tgharness at %s\n' "$bin_home/tgharness"
  case ":$PATH:" in
    *":$bin_home:"*) ;;
    *) printf 'Add %s to PATH if tgharness is not found.\n' "$bin_home" ;;
  esac
}

skill_target() {
  local agent="$1"
  case "$agent" in
    hermes-agent|hermes)
      printf '%s\n' "${HERMES_HOME:-$HOME/.hermes}/skills/telegram-harness"
      ;;
    codex)
      printf '%s\n' "$HOME/.agents/skills/telegram-harness"
      ;;
    claude-code|claude)
      printf '%s\n' "$HOME/.claude/skills/telegram-harness"
      ;;
    *)
      printf '%s\n' "$HOME/.agents/skills/telegram-harness"
      ;;
  esac
}

fallback_skill_install() {
  local agent="$1"
  local target
  target="$(skill_target "$agent")"
  rm -rf "$target"
  mkdir -p "$(dirname "$target")"
  cp -R "$ROOT/skills/telegram-harness" "$target"
  printf 'Installed telegram-harness skill for %s at %s\n' "$agent" "$target"
}

install_skill() {
  local agent="$1"
  # Re-adding from the current checkout makes installation and upgrades
  # deterministic even when the previous skill came from a local ZIP.
  if command -v npx >/dev/null 2>&1; then
    if npx -y skills add "$ROOT" --skill telegram-harness -g -a "$agent" -y --copy; then
      return
    fi
    printf 'npx skills could not install/update for %s; using direct copy fallback.\n' "$agent" >&2
  fi
  fallback_skill_install "$agent"
}

# Existing copies count as an installation target during upgrades, even if the
# corresponding agent executable is not currently on PATH.
detect_existing_skill_targets() {
  [[ -d "${HERMES_HOME:-$HOME/.hermes}/skills/telegram-harness" ]] && add_agent "hermes-agent"
  [[ -d "$HOME/.agents/skills/telegram-harness" ]] && add_agent "codex"
  [[ -d "$HOME/.claude/skills/telegram-harness" ]] && add_agent "claude-code"
  return 0
}

detect_agent_commands() {
  command -v hermes >/dev/null 2>&1 && add_agent "hermes-agent"
  command -v codex >/dev/null 2>&1 && add_agent "codex"
  command -v claude >/dev/null 2>&1 && add_agent "claude-code"
  return 0
}

if [[ "$UPGRADE" -eq 1 ]]; then
  printf 'Upgrading tgharness from this checkout; existing config and Telegram session files are preserved.\n'
  detect_existing_skill_targets
fi

# If the caller did not specify an agent, discover installed runtimes. During
# upgrades we also retain any existing skill targets discovered above.
if [[ ${#AGENTS[@]} -eq 0 || "$UPGRADE" -eq 1 ]]; then
  detect_agent_commands
fi

install_cli

resolve_tgharness() {
  if command -v tgharness >/dev/null 2>&1; then
    command -v tgharness
    return
  fi
  if [[ -x "${XDG_BIN_HOME:-$HOME/.local/bin}/tgharness" ]]; then
    printf '%s\n' "${XDG_BIN_HOME:-$HOME/.local/bin}/tgharness"
    return
  fi
  if command -v uv >/dev/null 2>&1; then
    local uv_bin
    uv_bin="$(uv tool dir --bin 2>/dev/null || true)"
    if [[ -n "$uv_bin" && -x "$uv_bin/tgharness" ]]; then
      printf '%s\n' "$uv_bin/tgharness"
      return
    fi
  fi
  return 1
}

TGHARNESS_BIN="$(resolve_tgharness)" || {
  echo "tgharness was installed but its executable could not be located." >&2
  exit 1
}

for agent in "${AGENTS[@]}"; do
  install_skill "$agent"
done

printf '\n✓ %s installed\n' "$("$TGHARNESS_BIN" --version)"

if [[ "$UPGRADE" -eq 1 ]]; then
  printf '✓ Upgrade complete. Existing config/session data was not removed.\n'
  printf '  Verify with: %s account list\n' "$TGHARNESS_BIN"
  printf '  Restart any long-running `tgharness serve` process so it uses the new code.\n'
  exit 0
fi

if [[ "$RUN_SETUP" -eq 1 ]]; then
  if [[ -t 0 && -t 1 ]]; then
    exec "$TGHARNESS_BIN" setup
  fi
  printf 'Run `%s setup` in an interactive terminal to configure and log in.\n' "$TGHARNESS_BIN"
fi
