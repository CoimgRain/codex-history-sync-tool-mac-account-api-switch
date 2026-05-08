# Codex History Sync Tool Mac - Account/API Switch

一个用于恢复 Codex Desktop 本地历史对话显示的小工具。

这个 macOS 版本重点解决一个常见问题：在 OpenAI/Plus 账号登录和 API 登录之间切换后，本地历史明明还在，但 Codex Desktop 侧边栏看不到旧对话。

## 这版新增

- 支持 OpenAI/Plus 账号登录：当 `config.toml` 没有 `model_provider` 时，会从 `auth.json` 和最近线程推断当前 provider。
- 支持 API 登录：如果 `config.toml` 写了 `model_provider`，仍优先使用配置里的当前 provider。
- 支持账号登录与 API 登录之间来回切换后刷新状态、一键同步历史。
- macOS `.app` 界面增加说明文字，直接双击即可使用。

## 直接下载使用

推荐下载发布包里的：

- `Codex History Sync Tool.app.zip`

下载后解压，双击 `Codex History Sync Tool.app` 即可打开。

如果 macOS 提示来自未验证开发者，可以在 Finder 中右键 app，选择“打开”，再确认一次。

## 这个工具能做什么

- 查看当前本机 Codex 历史线程属于哪些 provider
- 查看当前 Codex 使用的模型
- 一键把旧 provider / model 下的线程、会话元数据和侧边栏索引同步到当前登录方式
- 在同步前自动备份数据库、侧边栏索引和会话元数据
- 从备份恢复数据库
- 提供可直接双击运行的 macOS app bundle

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
- 系统可调用 `python3`
- Python 内置 `tkinter` 可用
- 本机存在 Codex Desktop 本地数据目录，通常是 `~/.codex`

## macOS 使用方式

### 方式一：双击 app

下载并解压：

```text
Codex History Sync Tool.app.zip
```

然后双击：

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
- 这个工具只修复本机可见性和 provider/model 归属，不会上传、同步或读取云端聊天记录

## 项目文件

- `sync_backend.py`：后端同步、备份、恢复逻辑
- `launch_ui_mac.py`：macOS 图形界面
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
