# FT FTP MCP

FT FTP MCP 为 AI Agent 提供 FTP / SFTP 文件访问能力。通过 14 个 MCP 工具，Agent 可以发现已配置的服务器、浏览目录、搜索文件、预览文本、上传下载，以及管理远程文件和目录。

支持在 Codex、WorkBuddy 和 DeepSeek Harness 中使用。服务器配置、凭据与访问范围由本机统一管理，多个客户端可使用同一套产品安装和配置。

- 产品与包名：`ft-ftp-mcp-stdio`
- Python 产品运行时：`0.3.1`
- npm 插件包：`0.3.2`（DSH 兼容性修复）
- 协议：FTP、SFTP
- 系统：Windows x64、macOS Apple Silicon / Intel
- 开源许可：MIT

## 主要能力

| 能力 | 工具 |
| --- | --- |
| 服务器发现与连接检查 | `list_servers`、`test_connection` |
| 浏览、搜索与文件信息 | `list_dir`、`search_files`、`get_file_info` |
| 文本预览 | `read_text_preview` |
| 文件与目录传输 | `upload_file`、`download_file`、`upload_dir`、`download_dir` |
| 文件与目录管理 | `make_dir`、`rename`、`move`、`delete` |

文件访问限制在预先配置的服务器根目录内。可为服务器启用只读模式；覆盖需要显式请求，删除需要 `confirm=true`。密码或私钥口令保存在系统凭据管理器，也可通过环境变量提供。

下载文件保存到本机暂存目录，工具返回路径、元数据和 SHA-256。使用 stdio 与 MCP 客户端通信，不额外开放本地服务端口。

## 安装准备

先从 [产品 0.3.1 发布页](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/releases/tag/tag_v0.3.1) 下载对应系统的产品安装包，按手册完成安装、`setup` 和 `doctor`：

- [Windows 安装手册](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/FTP-MCP-快速安装手册-windows-v0.3.1.md)
- [macOS 安装手册](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/FTP-MCP-快速安装手册-macOS-v0.3.1.md)（同一个安装包支持 Apple Silicon 和 Intel）

产品运行环境为 Python 3.12。本文中的 npm 包供 DeepSeek Harness 安装使用，调用已经安装的 Python 服务；安装 npm 包前仍需完成上述产品安装与服务器配置。

## 在 Codex / WorkBuddy 中使用

按照对应系统安装手册，将产品生成的 `codex-config.toml` 或 `workbuddy-mcp.json` 配置片段加入客户端，启用 MCP 服务即可。使用相同的 Python 产品运行时和服务器配置。

## 在 DeepSeek Harness 中使用

DSH 与官方 MCP 桥接器的版本声明为 `>=0.2.2-rc.1`，不设版本上限；目前实测 DSH `0.2.2-rc.1` 和 `0.2.2-rc.5`；CLI 使用 Node.js 24.9 及以上。发布状态见 [发布记录](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/DSH-Market-发布记录.md)。

### 桌面版

在插件管理页面的安装入口输入 `ft-ftp-mcp-stdio@0.3.2`，安装并启用。使用本地插件文件时，输入文件绝对路径，例如 `C:/Downloads/ft-ftp-mcp-stdio-0.3.2.tgz`。

桌面版的 `desktop` profile 由应用管理，安装、启用、禁用和卸载均通过桌面应用操作。不要使用 `dsh plugin --profile desktop ...`。

### CLI

退出目标 profile 后安装，以下以 `web` 为例：

```sh
dsh plugin --profile web add ft-ftp-mcp-stdio@0.3.2
dsh --profile web --dump-config
dsh --profile web
```

从本地插件文件安装时，把第一条命令替换为：

```sh
dsh plugin --profile web add ./ft-ftp-mcp-stdio-0.3.2.tgz
```

组合配置中应包含 `id: ft-ftp` 和 `name: ft-ftp-mcp-stdio`。工具名称以 `mcp__ft-ftp-mcp-stdio__` 开头。

安装后可对 Agent 说：“列出 FTP 服务器，并测试默认服务器的连接。”先确认 `list_servers` 返回正确配置，再调用 `test_connection` 和 `list_dir` 验证实际访问。

## 自定义运行路径

默认自动使用产品安装位置：

| 系统 | Python 路径 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\ft-ftp-mcp\venv\Scripts\python.exe` |
| macOS | `~/.ft-ftp-mcp/venv/bin/python` |

自定义安装时，可在 DSH 的 `id: ft-ftp` 条目下配置 `config.pythonPath` 和 `config.configPath`，分别指定 Python 解释器与服务器配置文件的绝对路径。也可在启动 DSH 的环境中设置 `FT_FTP_MCP_PYTHON` 和 `FT_FTP_MCP_CONFIG`；插件参数优先于环境变量。

未指定配置路径时使用 `~/.ft-ftp-mcp/config.json`。单次工具调用超时默认 120000 毫秒，可通过 `config.toolCallTimeoutMs` 调整。路径含空格无需额外拼接引号。

使用 `credential_env` 时，应在启动 DSH 的环境中提供配置引用的变量。不要把密码写入 DSH 配置或对话。更新配置或凭据环境变量后重启 profile。

## 诊断与卸载

- 找不到 Python 或产品版本不符：运行产品安装器，或修正 `pythonPath`。
- 连接、配置或认证失败：使用同一 Python 解释器执行 `-m ft_ftp_mcp_stdio doctor`。
- MCP 子进程异常退出：自动尝试重连，最多 3 次；修复原因后可重启 profile。
- CLI 卸载：退出 profile，执行 `dsh plugin --profile web remove ft-ftp-mcp-stdio`。
- 桌面版卸载：在插件管理页面移除 FT FTP MCP。

卸载 DSH 中的插件会保留产品运行时、服务器配置、系统凭据，以及 Codex / WorkBuddy 的配置。

## 开发与验证

在源码仓库根目录执行 `npm pack ./integrations/dsh --pack-destination .`，生成 `ft-ftp-mcp-stdio-0.3.2.tgz`。

Windows 已完成真实 DSH Desktop 工具注册、配置发现、连接和目录读取验证，以及本地 FTP 全工具、权限限制、崩溃重连和清理验证。macOS 路径逻辑已有测试，macOS 实机及 Keychain、DSH 链路上的真实 SFTP 尚未验证。详细结果见 [验证记录](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/DSH-Market-适配验证.md)。

版本范围遵循 npm SemVer：允许 0.2.2 的后续 rc 及更高正式版，但其他版本号的预发布版（例如 0.2.3-rc.1）不会自动匹配，需要另行声明。未实测的版本不代表已验证兼容。
