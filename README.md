# QuickTime Multi-Core & High-Resolution (2K/4K) Fix

[English](docs/PROBLEM_AND_SOLUTION.md) | [中文说明](docs/PROBLEM_AND_SOLUTION.md) | [AI Agent SOP 指导手册](docs/AGENT_GUIDE.md)

针对现代高核数高线程 CPU（AMD Ryzen 9 / Intel Core i7/i9，> 16 线程）在 Windows 系统下使用 Apple QuickTime 7 导出视频（特别是 Autodesk Maya 拍屏 Playblast 及 Adobe After Effects）遭遇崩溃、0KB 输出、`Disk Full (-34)`、`Error -2048` 及 2K/4K 分辨率闪退问题的**全自动修复解决方案**。

---

## 快速使用 (Zero-Config)

本项目无需任何外部第三方依赖，内置自包含的纯标准库脚本与批处理文件：

### 1. 一键全自动修复
直接双击运行根目录的：
```cmd
apply_fix.bat
```
*(或在管理员终端运行 `python scripts/patch_quicktime.py --apply`)*

**该脚本会自动执行：**
1. 自动定位本机 QuickTime 7 根目录及其编解码核心动态库。
2. 自动检索本机安装的**所有版本 Autodesk Maya**（Maya 2018 ~ 2027+）。
3. 自动创建所有被修改文件的**永久原始备份**（`.original`，绝不重复覆盖）。
4. 对 `QuickTimeH264.qtx` 实施重定位安全的动态核心感知补丁（1080p 限制 8 核，2K/4K 限制 4 核）。
5. 对所有 Maya 的 `quicktimeShim.exe` 及 `QuickTimePlayer.exe` 注入 **4GB 大内存感知（LargeAddressAware）**，根治 2K 内存耗尽。
6. 配置 Windows 注册表映像劫持项（IFEO）CPU 亲和度调度掩码。

### 2. 检查当前修复状态
双击运行：
```cmd
check_status.bat
```
输出各组件的补丁状态、4GB 大内存感知状态及注册表掩码。

### 3. 一键还原备份
如果需要完全恢复官方原版，双击运行：
```cmd
restore_backup.bat
```
自动将所有 `.original` 备份恢复为原版文件，并清除注册表 IFEO 调度配置。

---

## 项目结构

```text
quicktime-multicore-fix/
├── apply_fix.bat              # [一键执行] 应用所有补丁
├── restore_backup.bat          # [一键还原] 恢复全部官方原版文件
├── check_status.bat            # [状态检测] 查看当前系统的补丁状态
├── scripts/
│   └── patch_quicktime.py      # 核心自动化修补引擎（零外部依赖，纯原生 Python 3）
└── docs/
    ├── PROBLEM_AND_SOLUTION.md # 问题机理、底层逆向分析与修复方案白皮书
    └── AGENT_GUIDE.md          # 供其他大模型 Agent（Codex/Claude）自主排障的 SOP 指南
```

---

## 文档导航

* **[问题分析与解决方案深度白皮书 (`docs/PROBLEM_AND_SOLUTION.md`)](docs/PROBLEM_AND_SOLUTION.md)**：包含详细的汇编反汇编分析、Minidump 崩溃调用栈回溯、PE 重定位表保护机制、以及 1080p 与 2K 分辨率分水岭的完整底层推导。
* **[AI Agent 自动化排障 SOP 手册 (`docs/AGENT_GUIDE.md`)](docs/AGENT_GUIDE.md)**：专为 AI Agent（如 OpenAI Codex、Claude Code 等）编写的操作指南，详细列出机器环境感知、二进制特征码匹配、PE Header 修改及自动化验收验证的标准作业流程。

---

## 许可证与安全声明

* 本项目所有修改均只涉及去除 32 位老旧软件在现代多核环境与内存分配上的历史设计缺陷，不改动任何媒体数据编解码标准算法。
* 脚本在修改前强制创建 `.original` 原始副本，随时可无损一键还原。
