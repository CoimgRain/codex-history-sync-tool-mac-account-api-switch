# Open Source Notes

This repository is a macOS-focused derivative of two public MIT-licensed projects.

## Upstream projects

- Original project: `GODGOD126/codex-history-sync-tool`
  - URL: https://github.com/GODGOD126/codex-history-sync-tool
  - Scope: backend sync logic, Windows GUI entry, backup/restore workflow.
- macOS adaptation: `ruigod1/codex-history-sync-tool-mac`
  - URL: https://github.com/ruigod1/codex-history-sync-tool-mac
  - Scope: local macOS organization, `launch_ui_mac.py`, `launch_ui_mac.command`, and `.app` bundle.

## Changes in this version

- Added provider detection for OpenAI/Plus account login when `config.toml` does not contain `model_provider`.
- Kept API-login behavior intact by continuing to prefer `config.toml` when `model_provider` is present.
- Added fallback provider inference from recent local threads.
- Updated the macOS GUI copy to state that both OpenAI/Plus account login and API login are supported.
- Added an optional macOS LaunchAgent watcher that can trigger sync when Codex Desktop opens.
- Synced the fixed backend and GUI scripts into the bundled `Codex History Sync Tool.app`.

## Privacy note

The repository is intended to contain only generic source code, app bundle files, icons, documentation, and license material.

Do not commit local Codex data, including:

- `~/.codex/state_5.sqlite`
- `~/.codex/session_index.jsonl`
- `~/.codex/sessions`
- `~/.codex/auth.json`
- `~/.codex/config.toml`
- `~/.codex/history_sync_backups`
- screenshots, logs, or exports containing user-specific paths or thread content
- generated local LaunchAgent plists or watcher logs

Before publishing, run a repository-wide scan for personal paths, tokens, API keys, and local database names.
