from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


TOOL_ROOT = Path(__file__).resolve().parent
BACKEND_PATH = TOOL_ROOT / "sync_backend.py"


def run_backend(*args: str, codex_home: str | None = None) -> dict:
    cmd = [sys.executable, str(BACKEND_PATH), "--json"]
    if codex_home:
        cmd.extend(["--codex-home", codex_home])
    cmd.extend(args)
    completed = subprocess.run(cmd, capture_output=True, text=True)
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


class MacApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Codex 历史同步工具 (macOS)")
        self.root.geometry("900x680")
        self.root.minsize(900, 680)

        self.codex_home_var = tk.StringVar(value=str(Path.home() / ".codex"))
        self.current_status: dict | None = None
        self.backup_map: dict[str, str] = {}

        self._build_ui()
        self.refresh_status()

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
        ttk.Button(path_row, text="刷新状态", command=self.refresh_status).pack(side="left")

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
        ttk.Button(button_row, text="手动备份", command=self.manual_backup).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="恢复最新备份", command=self.restore_latest).pack(side="left", padx=(8, 0))
        ttk.Button(button_row, text="打开备份目录", command=self.open_backup_dir).pack(side="left", padx=(8, 0))

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

    def get_codex_home(self) -> str:
        return self.codex_home_var.get().strip()

    def refresh_status(self) -> None:
        try:
            payload = run_backend("status", codex_home=self.get_codex_home())
        except Exception as exc:
            messagebox.showerror("刷新失败", str(exc))
            self.append_log(f"刷新失败: {exc}")
            return

        self.current_status = payload
        provider_source = payload.get("current_provider_source")
        source_text = f" ({provider_source})" if provider_source else ""
        self.provider_label.config(text=f"当前 provider: {payload['current_provider']}{source_text}")
        self.model_label.config(text=f"当前模型: {payload.get('current_model') or '未读取到'}")
        self.summary_label.config(
            text=f"线程总数: {payload['total_threads']}    可同步线程: {payload['movable_threads']}"
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
            f"状态已刷新。当前 provider={payload['current_provider']}，可同步线程={payload['movable_threads']}。"
        )

    def sync_now(self) -> None:
        if not self.current_status:
            self.refresh_status()
        if self.current_status and int(self.current_status["movable_threads"]) <= 0:
            messagebox.showinfo("无需同步", "当前已经没有需要迁移到当前 provider 的线程。")
            self.append_log("同步跳过：没有需要迁移的线程。")
            return
        if not messagebox.askokcancel("确认同步", "将其他 provider 的线程统一归到当前 provider，且会先自动备份数据库。"):
            self.append_log("用户取消了同步。")
            return
        try:
            payload = run_backend("sync", codex_home=self.get_codex_home())
            self.append_log(f"同步完成。已移动 {payload['updated_rows']} 条线程。")
            self.append_log(f"备份文件: {payload['backup_path']}")
            self.refresh_status()
            messagebox.showinfo("同步完成", "同步完成。若历史列表没有立刻刷新，重开一次 Codex 即可。")
        except Exception as exc:
            messagebox.showerror("同步失败", str(exc))
            self.append_log(f"同步失败: {exc}")

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
