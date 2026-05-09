from __future__ import annotations

import argparse
import json
import os
import plistlib
import subprocess
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk


TOOL_ROOT = Path(__file__).resolve().parent
BACKEND_PATH = TOOL_ROOT / "sync_backend.py"
WATCHER_PATH = TOOL_ROOT / "auto_sync_watcher.py"
SETTINGS_PATH = Path.home() / "Library" / "Application Support" / "Codex History Sync Tool" / "settings.json"
AUTOSYNC_LABEL = "com.panrui.codex-history-sync-tool.autosync"
AUTOSYNC_PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{AUTOSYNC_LABEL}.plist"
AUTOSYNC_LOG_PATH = SETTINGS_PATH.parent / "autosync.log"
CODEX_BUNDLE_ID = "com.openai.codex"
CODEX_APP_PATH = "/Applications/Codex.app"
CODEX_RESTART_WAIT_SECONDS = 20
CODEX_QUIT_WAIT_SECONDS = 12
STARTUP_STATUS_SETTLE_SECONDS = 2.0
STARTUP_SYNC_RETRY_LIMIT = 3


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def run_backend_in_process(*args: str, codex_home: str | None = None) -> dict:
    import sync_backend

    command_args = list(args)
    command = command_args[0] if command_args else "status"
    paths = sync_backend.resolve_paths(codex_home)

    if command == "status":
        payload = sync_backend.get_status(paths)
    elif command == "sync":
        payload = sync_backend.sync_to_current_provider(paths)
    elif command == "backup":
        sync_backend.ensure_environment(paths)
        backup_started_at = time.monotonic()
        payload = {
            "action": "backup",
            "backup_path": str(sync_backend.make_backup(paths, "manual")),
            "timing": {"total_ms": sync_backend.elapsed_ms(backup_started_at)},
        }
    elif command == "restore":
        backup_path = None
        if "--backup" in command_args:
            index = command_args.index("--backup")
            if index + 1 >= len(command_args):
                raise RuntimeError("Missing value for --backup")
            backup_path = command_args[index + 1]
        payload = sync_backend.restore_backup(paths, backup_path)
    else:
        raise RuntimeError(f"Unsupported command: {command}")

    payload["ok"] = True
    return payload


def run_backend(*args: str, codex_home: str | None = None, timeout_seconds: int | None = None) -> dict:
    if is_frozen_app() or not BACKEND_PATH.exists():
        return run_backend_in_process(*args, codex_home=codex_home)

    cmd = [sys.executable, str(BACKEND_PATH), "--json"]
    if codex_home:
        cmd.extend(["--codex-home", codex_home])
    cmd.extend(args)
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        seconds = timeout_seconds if timeout_seconds is not None else "unknown"
        raise RuntimeError(f"后端执行超过 {seconds} 秒仍未返回，请稍后再试。") from exc
    text = (completed.stdout or completed.stderr).strip()
    if not text:
        raise RuntimeError("后端没有返回任何内容。")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"后端 JSON 解析失败: {exc}\n\n原始输出:\n{text}") from exc
    if completed.returncode != 0 or not payload.get("ok"):
        raise RuntimeError(payload.get("error") or text)
    return payload


def status_signature(payload: dict) -> tuple[object, ...]:
    return (
        payload.get("current_provider"),
        payload.get("current_model"),
        payload.get("total_threads"),
        payload.get("movable_threads"),
        payload.get("movable_database_threads"),
        payload.get("movable_session_threads"),
        payload.get("provider_movable_session_meta_entries"),
        payload.get("missing_session_index_entries"),
    )


def pending_work_count(payload: dict) -> int:
    return (
        int(payload.get("movable_threads") or 0)
        + int(payload.get("model_movable_threads") or 0)
        + int(payload.get("provider_movable_session_meta_entries") or 0)
    )


def load_settings() -> dict[str, object]:
    if not SETTINGS_PATH.exists():
        return {}
    try:
        payload = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_settings(settings: dict[str, object]) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_launchctl(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True, check=check)


def unload_autosync_agent() -> None:
    run_launchctl("bootout", f"gui/{os.getuid()}", str(AUTOSYNC_PLIST_PATH), check=False)


def install_autosync_agent(codex_home: str) -> None:
    if not is_frozen_app() and not WATCHER_PATH.exists():
        raise RuntimeError(f"找不到后台监听脚本: {WATCHER_PATH}")

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUTOSYNC_PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if is_frozen_app():
        program_arguments = [
            sys.executable,
            "--run-watcher",
            "--backend",
            "__bundled__",
            "--codex-home",
            codex_home,
            "--settings",
            str(SETTINGS_PATH),
            "--log",
            str(AUTOSYNC_LOG_PATH),
        ]
    else:
        program_arguments = [
            sys.executable,
            str(WATCHER_PATH),
            "--backend",
            str(BACKEND_PATH),
            "--codex-home",
            codex_home,
            "--settings",
            str(SETTINGS_PATH),
            "--log",
            str(AUTOSYNC_LOG_PATH),
        ]

    plist = {
        "Label": AUTOSYNC_LABEL,
        "ProgramArguments": program_arguments,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(AUTOSYNC_LOG_PATH),
        "StandardErrorPath": str(AUTOSYNC_LOG_PATH),
    }
    with AUTOSYNC_PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle)

    unload_autosync_agent()
    run_launchctl("bootstrap", f"gui/{os.getuid()}", str(AUTOSYNC_PLIST_PATH), check=True)


def uninstall_autosync_agent() -> None:
    unload_autosync_agent()
    if AUTOSYNC_PLIST_PATH.exists():
        AUTOSYNC_PLIST_PATH.unlink()


def is_codex_desktop_running() -> bool:
    completed = subprocess.run(
        ["pgrep", "-f", r"/Applications/Codex\.app/Contents/MacOS/Codex"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def restart_codex_desktop() -> str:
    script = r'''
on clickQuitConfirmation()
  set buttonNames to {"退出", "确认退出", "Quit", "OK", "确定", "继续退出"}
  repeat 25 times
    tell application "System Events"
      if exists process "Codex" then
        tell process "Codex"
          set frontmost to true
          repeat with buttonName in buttonNames
            try
              if exists button buttonName of window 1 then
                click button buttonName of window 1
                return "clicked"
              end if
            end try
            try
              if exists sheet 1 of window 1 then
                if exists button buttonName of sheet 1 of window 1 then
                  click button buttonName of sheet 1 of window 1
                  return "clicked"
                end if
              end if
            end try
          end repeat
        end tell
      end if
    end tell
    delay 0.2
  end repeat
  return "not_found"
end clickQuitConfirmation

tell application id "com.openai.codex" to quit
return clickQuitConfirmation()
'''
    completed = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
        timeout=8,
    )
    output = (completed.stdout or completed.stderr).strip()
    if completed.returncode != 0:
        raise RuntimeError(output or "无法通过 AppleScript 重启 Codex。")

    deadline = time.monotonic() + CODEX_QUIT_WAIT_SECONDS
    while time.monotonic() < deadline and is_codex_desktop_running():
        time.sleep(0.25)

    if is_codex_desktop_running():
        raise RuntimeError("Codex 已收到退出请求，但在限定时间内没有完全退出。请手动确认退出弹窗后再试。")

    open_result = subprocess.run(
        ["/usr/bin/open", "-a", CODEX_APP_PATH],
        capture_output=True,
        text=True,
        check=False,
    )
    if open_result.returncode != 0:
        raise RuntimeError((open_result.stderr or open_result.stdout).strip() or f"无法打开 {CODEX_APP_PATH}。")

    return f"restarted:{output or 'quit_requested'}"


def wait_for_codex_backend(timeout_seconds: int = CODEX_RESTART_WAIT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        completed = subprocess.run(
            ["pgrep", "-f", "Codex.app/Contents/Resources/codex app-server"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode == 0:
            return True
        time.sleep(0.5)
    return False


class MacApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Codex 历史同步工具 (macOS)")
        self.root.geometry("900x680")
        self.root.minsize(900, 680)

        self.settings = load_settings()
        self.codex_home_var = tk.StringVar(value=str(Path.home() / ".codex"))
        self.auto_sync_on_launch_var = tk.BooleanVar(
            value=bool(
                self.settings.get("auto_sync_when_codex_opens")
                or self.settings.get("auto_sync_on_launch")
            )
        )
        self.current_status: dict | None = None
        self.backup_map: dict[str, str] = {}
        self.refresh_in_progress = False
        self.startup_auto_sync_in_progress = False

        self._build_ui()
        self.root.after(100, self.startup_refresh_and_sync)
        self.root.after(800, self.ensure_autosync_agent_if_enabled)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=16)
        frame.pack(fill="both", expand=True)

        title = ttk.Label(frame, text="Codex 历史同步工具", font=("Helvetica", 18, "bold"))
        title.pack(anchor="w")

        warning = ttk.Label(
            frame,
            text=(
                "建议先关闭 Codex Desktop 再执行同步或恢复；mac 版会直接调用同一套后端逻辑。\n"
                "支持 OpenAI/Plus 账号登录和 API 登录，两种方式都可以刷新状态并同步历史。"
            ),
            justify="left",
        )
        warning.pack(anchor="w", pady=(6, 12))

        path_row = ttk.Frame(frame)
        path_row.pack(fill="x", pady=(0, 10))
        ttk.Label(path_row, text="Codex Home:").pack(side="left")
        ttk.Entry(path_row, textvariable=self.codex_home_var).pack(side="left", fill="x", expand=True, padx=(8, 8))
        self.refresh_button = ttk.Button(path_row, text="刷新状态", command=self.refresh_status)
        self.refresh_button.pack(side="left")

        auto_row = ttk.Frame(frame)
        auto_row.pack(fill="x", pady=(0, 10))
        ttk.Checkbutton(
            auto_row,
            text="打开 Codex Desktop 时自动刷新并同步到当前",
            variable=self.auto_sync_on_launch_var,
            command=self.save_auto_sync_setting,
        ).pack(anchor="w")

        self.provider_label = ttk.Label(frame, text="当前 provider:")
        self.provider_label.pack(anchor="w")
        self.model_label = ttk.Label(frame, text="当前模型:")
        self.model_label.pack(anchor="w")
        self.summary_label = ttk.Label(frame, text="线程总数:")
        self.summary_label.pack(anchor="w")
        self.db_label = ttk.Label(frame, text="数据库:")
        self.db_label.pack(anchor="w", pady=(0, 12))

        button_row = ttk.Frame(frame)
        button_row.pack(fill="x", pady=(0, 12))
        ttk.Button(button_row, text="一键同步到当前", command=self.sync_now).pack(side="left")
        ttk.Button(button_row, text="高级: 重启 Codex 并同步线程", command=self.restart_codex_and_sync).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="手动备份", command=self.manual_backup).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="恢复最新备份", command=self.restore_latest).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="打开备份目录", command=self.open_backup_dir).pack(side="left", padx=(8, 0))

        cc_switch_note = ttk.Label(
            frame,
            text=(
                "高级功能：不建议普通用户日常使用。\n"
                "使用前请先取消勾选“打开 Codex Desktop 时自动刷新并同步到当前”。\n"
                "CC Switch 切换后可用“高级: 重启 Codex 并同步线程”，工具会自动重启 Codex、刷新状态并同步线程。"
            ),
            justify="left",
            wraplength=820,
        )
        cc_switch_note.pack(anchor="w", pady=(0, 12))

        panes = ttk.Frame(frame)
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(0, weight=1)

        providers_box = ttk.LabelFrame(panes, text="Provider 统计", padding=8)
        providers_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.providers = ttk.Treeview(
            providers_box,
            columns=("provider", "count", "current"),
            show="headings",
            height=10,
        )
        self.providers.heading("provider", text="Provider")
        self.providers.heading("count", text="线程数")
        self.providers.heading("current", text="当前")
        self.providers.column("provider", width=180, anchor="w")
        self.providers.column("count", width=100, anchor="center")
        self.providers.column("current", width=80, anchor="center")
        self.providers.pack(fill="both", expand=True)

        backups_box = ttk.LabelFrame(panes, text="备份列表", padding=8)
        backups_box.grid(row=0, column=1, sticky="nsew")
        self.backup_list = tk.Listbox(backups_box)
        self.backup_list.pack(fill="both", expand=True)
        ttk.Button(backups_box, text="恢复选中备份", command=self.restore_selected).pack(anchor="w", pady=(8, 0))

        log_box = ttk.LabelFrame(frame, text="日志", padding=8)
        log_box.pack(fill="both", expand=True, pady=(12, 0))
        self.log = tk.Text(log_box, height=10, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def append_log_from_worker(self, text: str) -> None:
        self.root.after(0, lambda: self.append_log(text))

    def show_info_from_worker(self, title: str, message: str) -> None:
        self.root.after(0, lambda: messagebox.showinfo(title, message))

    def show_error_from_worker(self, title: str, message: str) -> None:
        self.root.after(0, lambda: messagebox.showerror(title, message))

    def get_codex_home(self) -> str:
        return self.codex_home_var.get().strip()

    def save_auto_sync_setting(self) -> None:
        enabled = bool(self.auto_sync_on_launch_var.get())
        self.settings["auto_sync_when_codex_opens"] = enabled
        self.settings.pop("auto_sync_on_launch", None)
        self.settings["codex_home"] = self.get_codex_home()
        if enabled:
            if not self.current_status:
                self.refresh_status()
            if self.current_status and self.current_status.get("current_provider"):
                self.settings["last_provider"] = str(self.current_status["current_provider"])
                self.settings["last_provider_seen_at"] = datetime.now().isoformat(timespec="seconds")
        try:
            save_settings(self.settings)
            if enabled:
                install_autosync_agent(self.get_codex_home())
            else:
                uninstall_autosync_agent()
        except Exception as exc:
            messagebox.showerror("保存设置失败", str(exc))
            self.append_log(f"保存设置失败: {exc}")
            return
        state = "开启" if enabled else "关闭"
        self.append_log(f"Codex 打开时自动同步已{state}。")

    def ensure_autosync_agent_if_enabled(self) -> None:
        if not self.auto_sync_on_launch_var.get():
            return
        try:
            install_autosync_agent(self.get_codex_home())
        except Exception as exc:
            self.append_log(f"后台自动同步监听启动失败: {exc}")

    def startup_refresh_and_sync(self) -> None:
        if self.startup_auto_sync_in_progress:
            return
        self.startup_auto_sync_in_progress = True
        self.refresh_button.configure(text="启动同步中...", state="disabled")
        self.append_log("启动后正在刷新状态并检查是否需要同步。")
        threading.Thread(target=self.startup_refresh_and_sync_worker, daemon=True).start()

    def startup_refresh_and_sync_worker(self) -> None:
        try:
            status = run_backend("status", codex_home=self.get_codex_home(), timeout_seconds=30)
            time.sleep(STARTUP_STATUS_SETTLE_SECONDS)
            second_status = run_backend("status", codex_home=self.get_codex_home(), timeout_seconds=30)
        except Exception as exc:
            self.root.after(0, lambda exc=exc: self.finish_startup_refresh_and_sync(error=exc))
            return
        if status_signature(status) != status_signature(second_status):
            self.root.after(0, lambda: self.append_log("启动状态仍在变化，已等待一次后使用最新状态继续同步。"))
        status = second_status

        pending_threads = pending_work_count(status)
        if pending_threads <= 0:
            self.root.after(0, lambda status=status: self.finish_startup_refresh_and_sync(status=status))
            return

        self.root.after(
            0,
            lambda pending_threads=pending_threads: self.append_log(
                f"启动后发现 {pending_threads} 个待同步或待更新线程，正在自动同步到当前。"
            ),
        )
        last_payload: dict | None = None
        last_error: Exception | None = None
        for attempt in range(1, STARTUP_SYNC_RETRY_LIMIT + 1):
            try:
                payload = run_backend("sync", codex_home=self.get_codex_home(), timeout_seconds=120)
                last_payload = payload
                after_status = payload.get("status") if isinstance(payload.get("status"), dict) else None
                remaining = pending_work_count(after_status or {})
                if remaining <= 0:
                    break
                self.root.after(
                    0,
                    lambda attempt=attempt, remaining=remaining: self.append_log(
                        f"启动自动同步第 {attempt} 次后仍有 {remaining} 个待同步或待更新线程，准备重试。"
                    ),
                )
                time.sleep(STARTUP_STATUS_SETTLE_SECONDS)
            except Exception as exc:
                last_error = exc
                break

        if last_payload is not None:
            self.root.after(0, lambda payload=last_payload: self.finish_startup_refresh_and_sync(sync_payload=payload))
            return
        self.root.after(0, lambda status=status, exc=last_error: self.finish_startup_refresh_and_sync(status=status, error=exc))

    def finish_startup_refresh_and_sync(
        self,
        status: dict | None = None,
        sync_payload: dict | None = None,
        error: Exception | None = None,
    ) -> None:
        try:
            if status is not None:
                self.apply_status_payload(status)
            if sync_payload is not None:
                self.append_log(f"启动自动同步完成。已移动 {sync_payload['updated_rows']} 条线程。")
                self.append_log(f"已更新 {sync_payload.get('updated_session_meta_entries', 0)} 条 session 元数据。")
                self.append_log(f"备份文件: {sync_payload['backup_path']}")
                payload_status = sync_payload.get("status")
                if isinstance(payload_status, dict):
                    self.apply_status_payload(payload_status)
                else:
                    self.refresh_status()
            if error is not None:
                messagebox.showerror("启动自动同步失败", str(error))
                self.append_log(f"启动自动同步失败: {error}")
        finally:
            self.startup_auto_sync_in_progress = False
            if not self.refresh_in_progress:
                self.refresh_button.configure(text="刷新状态", state="normal")

    def refresh_status(self) -> None:
        if self.refresh_in_progress:
            self.append_log("刷新状态仍在进行中，请稍等。")
            return
        self.refresh_in_progress = True
        self.refresh_button.configure(text="正在刷新...", state="disabled")
        self.append_log("正在刷新状态。")
        threading.Thread(target=self.refresh_status_worker, daemon=True).start()

    def refresh_status_worker(self) -> None:
        try:
            payload = run_backend("status", codex_home=self.get_codex_home(), timeout_seconds=30)
        except Exception as exc:
            self.root.after(0, lambda exc=exc: self.finish_refresh_status(error=exc))
            return

        self.root.after(0, lambda payload=payload: self.finish_refresh_status(payload=payload))

    def finish_refresh_status(self, payload: dict | None = None, error: Exception | None = None) -> None:
        try:
            if error is not None:
                messagebox.showerror("刷新失败", str(error))
                self.append_log(f"刷新失败: {error}")
                return
            if payload is not None:
                self.apply_status_payload(payload)
        finally:
            self.refresh_in_progress = False
            self.refresh_button.configure(text="刷新状态", state="normal")

    def refresh_status_with_result(self) -> bool:
        try:
            payload = run_backend("status", codex_home=self.get_codex_home(), timeout_seconds=30)
        except Exception as exc:
            messagebox.showerror("刷新失败", str(exc))
            self.append_log(f"刷新失败: {exc}")
            return False

        self.apply_status_payload(payload)
        return True

    def apply_status_payload(self, payload: dict) -> None:
        self.current_status = payload
        provider_source = payload.get("current_provider_source")
        source_text = f" ({provider_source})" if provider_source else ""
        self.provider_label.config(text=f"当前 provider: {payload['current_provider']}{source_text}")
        self.model_label.config(text=f"当前模型: {payload.get('current_model') or '未读取到'}")
        self.summary_label.config(
            text=(
                f"线程总数: {payload['total_threads']}    待处理线程: {payload['movable_threads']}    "
                f"provider 待同步: {payload.get('provider_movable_threads', 0)}    "
                f"model 待更新: {payload.get('model_movable_threads', 0) or 0}    "
                f"session meta 待修复: {payload.get('provider_movable_session_meta_entries', 0)} 条"
            )
        )
        self.db_label.config(text=f"数据库: {payload['db_path']}")

        for item in self.providers.get_children():
            self.providers.delete(item)
        for row in payload["provider_counts"]:
            current = "是" if row["provider"] == payload["current_provider"] else ""
            self.providers.insert("", "end", values=(row["provider"], row["count"], current))

        self.backup_list.delete(0, "end")
        self.backup_map = {}
        for backup in payload["backups"]:
            label = f"{backup['modified_at']}    {backup['name']}"
            self.backup_map[label] = backup["path"]
            self.backup_list.insert("end", label)

        self.append_log(
            f"状态已刷新。当前 provider={payload['current_provider']}，待处理线程={payload['movable_threads']}。"
        )

    def sync_now(self) -> None:
        self.append_log("开始同步前先刷新状态。")
        if not self.refresh_status_with_result():
            return
        if self.current_status and pending_work_count(self.current_status) <= 0:
            messagebox.showinfo("无需同步", "当前已经没有需要同步或更新的线程。")
            self.append_log("同步跳过：没有需要同步或更新的线程。")
            return
        if not messagebox.askokcancel("确认同步", "将其他 provider 的线程统一归到当前 provider，且会先自动备份数据库。"):
            self.append_log("用户取消了同步。")
            return
        self.run_sync(show_success_message=True)

    def run_sync(self, show_success_message: bool = False) -> bool:
        try:
            payload = run_backend("sync", codex_home=self.get_codex_home(), timeout_seconds=120)
            self.append_log(f"同步完成。已移动 {payload['updated_rows']} 条线程。")
            self.append_log(f"已更新 {payload.get('updated_session_meta_entries', 0)} 条 session 元数据。")
            self.append_log(f"备份文件: {payload['backup_path']}")
            self.refresh_status()
            if show_success_message:
                messagebox.showinfo("同步完成", "同步完成。若历史列表没有立刻刷新，重开一次 Codex 即可。")
            return True
        except Exception as exc:
            messagebox.showerror("同步失败", str(exc))
            self.append_log(f"同步失败: {exc}")
            return False

    def restart_codex_and_sync(self) -> None:
        threading.Thread(target=self.restart_codex_and_sync_worker, daemon=True).start()

    def restart_codex_and_sync_worker(self) -> None:
        if self.auto_sync_on_launch_var.get():
            self.root.after(0, lambda: self.auto_sync_on_launch_var.set(False))
            self.settings["auto_sync_when_codex_opens"] = False
            self.settings.pop("auto_sync_on_launch", None)
            try:
                save_settings(self.settings)
                uninstall_autosync_agent()
                self.append_log_from_worker("已关闭“打开 Codex Desktop 时自动刷新并同步到当前”，避免与手动重启同步冲突。")
            except Exception as exc:
                self.show_error_from_worker("关闭自动同步失败", str(exc))
                self.append_log_from_worker(f"关闭自动同步失败: {exc}")
                return

        self.append_log_from_worker("正在重启 Codex Desktop。")
        try:
            result = restart_codex_desktop()
            self.append_log_from_worker(f"Codex 已重新打开: {result}")
        except Exception as exc:
            self.show_error_from_worker("重启 Codex 失败", str(exc))
            self.append_log_from_worker(f"重启 Codex 失败: {exc}")
            return

        if wait_for_codex_backend():
            self.append_log_from_worker("Codex 后台服务已启动，正在刷新状态。")
        else:
            self.append_log_from_worker("未在预期时间内检测到 Codex 后台服务，仍继续刷新状态。")

        try:
            status = run_backend("status", codex_home=self.get_codex_home(), timeout_seconds=30)
        except Exception as exc:
            self.show_error_from_worker("刷新失败", str(exc))
            self.append_log_from_worker(f"重启后同步跳过：无法读取当前状态。{exc}")
            return

        self.root.after(0, lambda status=status: self.apply_status_payload(status))
        pending_threads = pending_work_count(status)
        if pending_threads <= 0:
            self.append_log_from_worker("重启后同步跳过：没有需要同步或更新的线程。")
            self.show_info_from_worker("无需同步", "Codex 已重启，当前没有需要同步的线程。")
            return

        self.append_log_from_worker(f"重启后发现 {pending_threads} 个待同步或待更新线程，正在同步。")
        try:
            payload = run_backend("sync", codex_home=self.get_codex_home(), timeout_seconds=120)
        except Exception as exc:
            self.show_error_from_worker("同步失败", str(exc))
            self.append_log_from_worker(f"同步失败: {exc}")
            return

        self.append_log_from_worker(f"同步完成。已移动 {payload['updated_rows']} 条线程。")
        self.append_log_from_worker(f"已更新 {payload.get('updated_session_meta_entries', 0)} 条 session 元数据。")
        self.append_log_from_worker(f"备份文件: {payload['backup_path']}")
        self.root.after(0, self.refresh_status)
        self.show_info_from_worker("完成", "Codex 已重启，线程已同步到当前。")

    def manual_backup(self) -> None:
        try:
            payload = run_backend("backup", codex_home=self.get_codex_home())
            self.append_log(f"手动备份完成: {payload['backup_path']}")
            self.refresh_status()
        except Exception as exc:
            messagebox.showerror("备份失败", str(exc))
            self.append_log(f"备份失败: {exc}")

    def restore_latest(self) -> None:
        if not messagebox.askokcancel("确认恢复", "将恢复最新备份，并在恢复前自动创建安全备份。"):
            self.append_log("用户取消了恢复最新备份。")
            return
        try:
            payload = run_backend("restore", codex_home=self.get_codex_home())
            self.append_log(f"已恢复最新备份: {payload['restored_from']}")
            self.append_log(f"恢复前安全备份: {payload['safety_backup']}")
            self.refresh_status()
            messagebox.showinfo("恢复完成", "恢复完成。建议重开一次 Codex 再看历史列表。")
        except Exception as exc:
            messagebox.showerror("恢复失败", str(exc))
            self.append_log(f"恢复失败: {exc}")

    def restore_selected(self) -> None:
        selection = self.backup_list.curselection()
        if not selection:
            messagebox.showwarning("未选择备份", "先在右侧选一个备份。")
            return
        label = self.backup_list.get(selection[0])
        backup_path = self.backup_map.get(label)
        if not backup_path:
            messagebox.showerror("恢复失败", "无法解析选中的备份路径。")
            return
        if not messagebox.askokcancel("确认恢复", f"将恢复这个备份：\n{backup_path}\n\n恢复前会先自动生成一份安全备份。"):
            self.append_log("用户取消了恢复。")
            return
        try:
            payload = run_backend("restore", "--backup", backup_path, codex_home=self.get_codex_home())
            self.append_log(f"恢复完成。来源备份: {payload['restored_from']}")
            self.append_log(f"恢复前安全备份: {payload['safety_backup']}")
            self.refresh_status()
            messagebox.showinfo("恢复完成", "恢复完成。建议重开一次 Codex 再看历史列表。")
        except Exception as exc:
            messagebox.showerror("恢复失败", str(exc))
            self.append_log(f"恢复失败: {exc}")

    def open_backup_dir(self) -> None:
        if not self.current_status:
            self.refresh_status()
        backup_dir = self.current_status.get("backup_dir") if self.current_status else None
        if not backup_dir:
            messagebox.showerror("打开失败", "还没有读取到备份目录。")
            return
        path = Path(backup_dir)
        path.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(path)], check=False)
        self.append_log(f"已打开备份目录: {path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="macOS GUI for Codex history sync tool")
    parser.add_argument("--smoke-test", action="store_true", help="Run a backend connectivity check and exit")
    parser.add_argument("--codex-home", help="Override Codex home directory for smoke testing")
    return parser.parse_args()


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--run-backend":
        import sync_backend

        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return sync_backend.main()

    if len(sys.argv) > 1 and sys.argv[1] == "--run-watcher":
        import auto_sync_watcher

        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return auto_sync_watcher.main()

    args = parse_args()
    if args.smoke_test:
        payload = run_backend("status", codex_home=args.codex_home)
        print(
            f"Smoke test OK: provider={payload['current_provider']} "
            f"movable_threads={payload['movable_threads']}"
        )
        return 0

    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("aqua")
    except tk.TclError:
        pass
    MacApp(root)

    # Try hard to bring the window to the foreground on macOS launch.
    root.update_idletasks()
    root.deiconify()
    root.lift()
    try:
        root.focus_force()
    except tk.TclError:
        pass
    try:
        root.attributes("-topmost", True)
        root.after(250, lambda: root.attributes("-topmost", False))
    except tk.TclError:
        pass
    try:
        subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to set frontmost of the first process whose unix id is '
                f'{os.getpid()} to true',
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
