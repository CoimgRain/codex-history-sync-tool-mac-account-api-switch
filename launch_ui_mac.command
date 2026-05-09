#!/bin/zsh
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_LAUNCHER="$SCRIPT_DIR/Codex History Sync Tool.app/Contents/MacOS/CodexHistorySyncTool"

if [[ -f "$APP_LAUNCHER" && ! -x "$APP_LAUNCHER" ]]; then
  chmod +x "$APP_LAUNCHER" 2>/dev/null || true
fi

if [[ -x "$APP_LAUNCHER" && "${CODEX_HISTORY_SYNC_USE_SOURCE:-}" != "1" ]]; then
  exec "$APP_LAUNCHER" "$@"
fi

PYTHON_BIN="$(command -v python3 2>/dev/null || true)"
if [[ -n "$PYTHON_BIN" ]] && "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import tkinter as tk
root = tk.Tk()
root.withdraw()
root.update_idletasks()
root.destroy()
PY
then
  exec "$PYTHON_BIN" "$SCRIPT_DIR/launch_ui_mac.py" "$@"
fi

osascript <<'OSA' >/dev/null 2>&1 || true
display dialog "Codex History Sync Tool 找不到可用的 Python 3 + tkinter 图形环境。\n\n请双击 Codex History Sync Tool.app，或安装 python.org 的 macOS Python 3 后重试。" buttons {"OK"} default button "OK" with icon caution
OSA
exit 1
