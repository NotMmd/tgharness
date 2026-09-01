# Changelog

## 0.5.2

- Add a dedicated copy/paste Agent update prompt near the top of README.
- Make the upgrade workflow explicitly preserve account registry, configuration, Telegram sessions, and existing authorizations.
- Document skill refresh, `tgharness serve` restart, and post-upgrade account/version verification.
- Keep the bundled Agent Skill version aligned with the package release.

## 0.5.1

- Add a first-class `--upgrade` installer mode for in-place upgrades from published `main`.
- Preserve existing XDG config, data, and Telegram session files during upgrades.
- Detect and refresh existing Hermes, Codex, and Claude Code copies of the bundled `telegram-harness` skill.
- Document the 0.4.x single-session to 0.5.x multi-account compatibility path.
- Add explicit post-upgrade verification and long-running server restart guidance.

## 0.5.0

- Add named multi-account/session registry and account targeting.
- Add account enable/disable/default/remove/login management.
- Add live account identity/profile inspection and profile-photo access/downloads.
- Add multi-account routing through direct and IPC execution with per-account JSON results.
- Keep runtime method discovery, universal Client calls, Raw MTProto, and Python escape-hatch access.
