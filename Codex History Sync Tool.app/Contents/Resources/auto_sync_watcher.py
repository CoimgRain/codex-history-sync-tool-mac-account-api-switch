from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


DEFAULT_POLL_SECONDS = 3.0
DEFAULT_INITIAL_DELAY_SECONDS = 2.0


def append_log(path: Path | None, message: str) -> None:
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    if path is None:
        print(line, flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def codex_desktop_pids() -> set[int]:
    completed = subprocess.run(["ps", "-axo", "pid,args"], capture_output=True, text=True, check=False)
    pids: set[int] = set()
    for line in completed.stdout.splitlines()[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, args = stripped.partition(" ")
        try:
            pid = int(pid_text)
        except ValueError:
            continue
        if "Codex.app/Contents/MacOS/Codex" in args and "Codex History Sync Tool.app" not in args:
            pids.add(pid)
    return pids


def run_backend(backend: Path, command: str, codex_home: str | None) -> dict[str, object]:
    cmd = [sys.executable, str(backend), "--json"]
    if codex_home:
        cmd.extend(["--codex-home", codex_home])
    cmd.append(command)
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    text = (completed.stdout or completed.stderr).strip()
    if not text:
        raise RuntimeError("backend returned no output")
    payload = json.loads(text)
    if completed.returncode != 0 or not payload.get("ok"):
        raise RuntimeError(str(payload.get("error") or text))
    return payload


def sync_if_needed(backend: Path, codex_home: str | None, log_path: Path | None) -> None:
    status = run_backend(backend, "status", codex_home)
    movable_threads = int(status.get("movable_threads") or 0)
    current_provider = status.get("current_provider")
    append_log(log_path, f"Codex opened: provider={current_provider}, movable_threads={movable_threads}")
    if movable_threads <= 0:
        return

    payload = run_backend(backend, "sync", codex_home)
    append_log(
        log_path,
        f"Auto sync completed: updated_rows={payload.get('updated_rows')}, "
        f"updated_session_files={payload.get('updated_session_files')}, backup={payload.get('backup_path')}",
    )


def watch(args: argparse.Namespace) -> int:
    backend = Path(args.backend).expanduser()
    log_path = Path(args.log).expanduser() if args.log else None
    if not backend.exists():
        append_log(log_path, f"backend does not exist: {backend}")
        return 1

    initial_open = bool(codex_desktop_pids())
    previous_open = False
    append_log(log_path, f"watcher started; codex_open={initial_open}")

    if args.once:
        if initial_open:
            time.sleep(args.initial_delay)
            sync_if_needed(backend, args.codex_home, log_path)
        return 0

    while True:
        is_open = bool(codex_desktop_pids())
        if is_open and not previous_open:
            time.sleep(args.initial_delay)
            try:
                sync_if_needed(backend, args.codex_home, log_path)
            except Exception as exc:
                append_log(log_path, f"auto sync failed: {exc}")
        previous_open = is_open
        time.sleep(args.poll)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch Codex Desktop launches and auto-sync local history.")
    parser.add_argument("--backend", required=True, help="Path to sync_backend.py")
    parser.add_argument("--codex-home", help="Codex home directory; defaults to backend default")
    parser.add_argument("--log", help="Log file path")
    parser.add_argument("--poll", type=float, default=DEFAULT_POLL_SECONDS, help="Process polling interval")
    parser.add_argument("--initial-delay", type=float, default=DEFAULT_INITIAL_DELAY_SECONDS)
    parser.add_argument("--once", action="store_true", help="Run one detection pass and exit")
    return parser.parse_args()


def main() -> int:
    try:
        return watch(parse_args())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
