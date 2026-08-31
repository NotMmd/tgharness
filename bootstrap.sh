#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/NotMmd/tgharness.git"
ARCHIVE_URL="https://github.com/NotMmd/tgharness/archive/refs/heads/main.tar.gz"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if command -v git >/dev/null 2>&1; then
  git clone --depth 1 "$REPO_URL" "$TMP/tgharness" >/dev/null
else
  command -v curl >/dev/null 2>&1 || { echo "git or curl is required" >&2; exit 1; }
  command -v tar >/dev/null 2>&1 || { echo "tar is required" >&2; exit 1; }
  curl -fsSL "$ARCHIVE_URL" | tar -xz -C "$TMP"
  mv "$TMP/tgharness-main" "$TMP/tgharness"
fi

"$TMP/tgharness/install.sh" "$@"
