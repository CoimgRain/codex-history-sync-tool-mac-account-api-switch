#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_LAUNCHER="$SCRIPT_DIR/Codex History Sync Tool.app/Contents/MacOS/CodexHistorySyncTool"

if [[ -x "$APP_LAUNCHER" && "${CODEX_HISTORY_SYNC_USE_SOURCE:-}" != "1" ]]; then
  exec "$APP_LAUNCHER" "$@"
fi

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_DIR/launch_ui_mac.py" "$@"
fi

osascript <<'OSA' >/dev/null 2>&1 || true
display dialog "Codex History Sync Tool 找不到 python3。\n\n请双击 Codex History Sync Tool.app，或安装 python.org 的 macOS Python 3 后重试。" buttons {"OK"} default button "OK" with icon caution
OSA
exit 1
