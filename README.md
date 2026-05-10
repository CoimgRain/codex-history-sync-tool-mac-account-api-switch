# Codex History Sync Tool Mac - Account/API Switch

一个用于恢复 Codex Desktop 本地历史对话显示的小工具。

这个 macOS 版本重点解决一个常见问题：在 OpenAI/Plus 账号登录和 API 登录之间切换后，本地历史明明还在，但 Codex Desktop 侧边栏看不到旧对话。

## 这版新增

- 支持 OpenAI/Plus 账号登录：当 `config.toml` 没有 `model_provider` 时，会从 `auth.json` 和最近线程推断当前 provider。
- 支持 API 登录：如果 `config.toml` 写了 `model_provider`，仍优先使用配置里的当前 provider。
- 支持账号登录与 API 登录之间来回切换后刷新状态、一键同步历史。
- 一键同步会先刷新最新状态：只要存在可同步线程就同步，没有可同步线程就跳过。
- 支持勾选“打开 Codex Desktop 时自动刷新并同步到当前”：开启后会安装本机 LaunchAgent，在 Codex Desktop 启动时自动刷新状态，并在存在可同步线程时自动同步。
- 提供高级功能“重启 Codex 并同步线程”：适合 CC Switch 或登录方式切换后使用，会自动重启 Codex、刷新状态并同步线程；不建议日常用户频繁使用。
- 高级重启同步按钮已改为后台执行，避免 Codex 关闭或重开过程导致工具窗口卡死。
- 刷新状态改为后台执行并显示进度；重启同步和自动同步增加超时保护，避免 Codex 刚启动时看起来没有反应。
- macOS `.app` 界面增加说明文字，直接双击即可使用。
- v1.5.3 起，启动器会实际测试 `Python 3 + tkinter` 能否创建 macOS 图形窗口；如果不可用，会询问是否自动安装 python.org 官方 Python 3.13.13，安装完成后会自动继续打开工具。
- v1.6.0 起，发布包分为轻量版和内置 Python 版。内置版不依赖用户本机 Python，适合没有 Python 环境或遇到闪退的用户。
- v1.6.1 修复内置 Python 版发布包缺少后端脚本时的启动 JSON 解析失败问题。

## 直接下载使用

发布包有 3 个 DMG，按下面规则下载：

| 使用场景 | 下载文件 |
| --- | --- |
| 已经有可用的 Python 3 + tkinter，想下载最小体积 | `Codex-History-Sync-Tool-v1.6.1-Lite.dmg` |
| 没有 Python 环境，或者轻量版双击闪退；Mac 是 Apple 芯片（M1/M2/M3/M4 等） | `Codex-History-Sync-Tool-v1.6.1-Apple-Silicon.dmg` |
| 没有 Python 环境，或者轻量版双击闪退；Mac 是 Intel 处理器 | `Codex-History-Sync-Tool-v1.6.1-Intel.dmg` |

下载后打开 DMG，把 `Codex History Sync Tool.app` 拖到 `Applications`，再双击打开。

不知道自己的 Mac 是哪种芯片，可以点左上角苹果菜单 -> “关于本机”。显示“芯片 Apple M...”就选 Apple Silicon；显示“处理器 Intel”就选 Intel。

如果 macOS 提示来自未验证开发者，可以在 Finder 中右键 app，选择“打开”，再确认一次。

如果 DMG 或 app 仍然打不开，可以打开系统设置里的“隐私与安全性”，在安全提示处选择“仍要打开”。

如果双击后窗口一闪而过，通常是这台 Mac 没有可用的 `python3 + tkinter` 图形环境。v1.5.3 起启动器不再只检查 `import tkinter`，而是会实际创建一个隐藏 Tk 窗口；这可以避开 CommandLineTools Python 这类“能导入 tkinter、但创建窗口时崩溃”的环境。检测失败时，启动器会弹出提示，用户确认后会从 python.org 下载并安装官方 Python 3.13.13；安装过程会由 macOS 要求管理员授权。启动器日志会写到：

```text
~/Library/Logs/Codex History Sync Tool/launcher.log
```

如果自动安装失败，可以按日志提示手动安装 python.org 的 macOS Python 3 后再打开工具。

如果不想让用户下载或安装任何 Python，直接使用 Apple Silicon 或 Intel 的内置 Python 版。内置版会使用 app 自己打包的 Python/Tk，不会修改系统 Python，也不会和用户电脑已有 Python 冲突。

注意：本工具没有使用 Apple Developer ID 签名和公证，所以首次打开时 macOS 可能会拦截未验证开发者应用。这种情况不是程序崩溃，按上面的“右键打开”或“隐私与安全性”方式放行即可。如果是窗口一闪而过或没有任何提示，优先查看上面的启动器日志。

## 这个工具能做什么

- 查看当前本机 Codex 历史线程属于哪些 provider
- 查看当前 Codex 使用的模型
- 一键把旧 provider / model 下的线程、会话元数据和侧边栏索引同步到当前登录方式
- 在同步前自动备份数据库、侧边栏索引和会话元数据
- 从备份恢复数据库
- 提供可直接双击运行的 macOS app bundle
- 可选后台监听 Codex Desktop 启动，并在启动时自动刷新状态；如果存在可同步线程，会自动同步
- 可选高级重启同步：自动关闭并重新打开 Codex Desktop，随后刷新状态并同步线程

## 适用场景

- 从 API 登录切换到 OpenAI/Plus 账号登录后，旧历史不显示
- 从 OpenAI/Plus 账号登录切换回 API 登录后，旧历史不显示
- 切换了不同 API、provider、模型或登录方式
- 本地历史文件仍在，但 Codex Desktop 左侧历史列表为空或不完整

## 不适用的场景

- 云端账号之间的聊天记录互相同步
- 本地历史文件已经被删除
- 不同电脑之间迁移聊天记录

## macOS 运行环境

- macOS 11 或更高版本
- 轻量版需要系统可调用 `python3`，且 Python 内置 `tkinter` 可创建图形窗口
- Apple Silicon / Intel 内置版不需要用户预先安装 Python
- 本机存在 Codex Desktop 本地数据目录，通常是 `~/.codex`

## macOS 使用方式

### 方式一：双击 app

下载并解压：

```text
Codex-History-Sync-Tool-v1.6.1-Lite.dmg
Codex-History-Sync-Tool-v1.6.1-Apple-Silicon.dmg
Codex-History-Sync-Tool-v1.6.1-Intel.dmg
```

打开 DMG 后把 app 拖到 Applications，然后双击：

```text
Codex History Sync Tool.app
```

### 方式二：从源码启动

```bash
python3 ./launch_ui_mac.py
```

或者：

```bash
./launch_ui_mac.command
```

`launch_ui_mac.command` 会优先调用内置 `.app` 的启动器，因此也会复用 Python/tkinter 检测、日志和自动安装提示。开发者如果想强制运行源码脚本，可以使用：

```bash
CODEX_HISTORY_SYNC_USE_SOURCE=1 ./launch_ui_mac.command
```

## 命令行用法

查看当前状态：

```bash
python3 ./sync_backend.py --json status
```

执行同步：

```bash
python3 ./sync_backend.py --json sync
```

手动创建备份：

```bash
python3 ./sync_backend.py --json backup
```

从最新备份恢复：

```bash
python3 ./sync_backend.py --json restore
```

## 备份说明

- 每次同步前都会自动创建一份备份
- 每次恢复前也会先创建一份安全备份
- 备份默认保存在 `~/.codex/history_sync_backups`
- 备份会同时保存 `session_index.jsonl` 和会话文件首行元数据，恢复时会一起还原

## 使用建议

- 同步前建议先关闭或暂停 Codex Desktop 正在运行的任务
- 如果 Codex Desktop 正在写入数据库，工具会等待数据库空闲后继续
- 如果同步完成后历史列表没有立刻刷新，重开一次 Codex Desktop
- 自动同步开关会在本机 `~/Library/LaunchAgents` 下安装或移除 LaunchAgent；它只监听本机 Codex Desktop 是否启动，并调用本工具后端，不会上传任何数据
- 如果要使用“高级: 重启 Codex 并同步线程”，建议先取消勾选“打开 Codex Desktop 时自动刷新并同步到当前”，避免手动重启同步和后台自动同步同时触发
- “高级: 重启 Codex 并同步线程”不建议普通用户日常使用；它主要用于 CC Switch 或账号/API 切换后，需要让 Codex 重启并立刻同步历史的场景
- 这个工具只修复本机可见性和 provider/model 归属，不会上传、同步或读取云端聊天记录

## 项目文件

- `sync_backend.py`：后端同步、备份、恢复逻辑
- `launch_ui_mac.py`：macOS 图形界面
- `auto_sync_watcher.py`：监听 Codex Desktop 启动并触发自动同步的后台脚本
- `launch_ui_mac.command`：macOS 双击命令入口
- `Codex History Sync Tool.app`：macOS app bundle
- `launch_ui.ps1`：上游 Windows 图形界面入口

## 上游来源与致谢

本项目基于两个公开 MIT 项目整理和修改：

- 原始项目：[`GODGOD126/codex-history-sync-tool`](https://github.com/GODGOD126/codex-history-sync-tool)
- macOS 适配项目：[`ruigod1/codex-history-sync-tool-mac`](https://github.com/ruigod1/codex-history-sync-tool-mac)

本版本在 macOS 适配版基础上增加了 OpenAI/Plus 账号登录与 API 登录切换场景下的 provider 推断逻辑，并更新了 macOS app 内置脚本和说明。

## 免责声明

这个工具直接操作本机 Codex 的本地状态数据库。虽然已经做了自动备份，但仍建议你在使用前理解它的作用，并自行确认本地数据目录状态。

本工具不会收集、上传或提交你的个人 Codex 数据；发布仓库只包含通用源码、app bundle 和说明文件。
