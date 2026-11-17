# FT FTP · DSH Market 适配

插件包 `dsh-ft-ftp@0.1.0` 将已经安装的 `ft-ftp-mcp-stdio@0.3.1` 接入 DeepSeek Harness。它使用官方 `@deepseek-ai/dsh-mcp-client`，保留原服务的全部 14 个工具和权限限制，不复制 FTP/SFTP 实现。

## 安装前准备（Windows / macOS 通用）

1. 从 [产品 0.3.1 发布页](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/releases/tag/tag_v0.3.1) 下载并安装对应系统的产品包，按照 [Windows 手册](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/FTP-MCP-快速安装手册-windows-v0.3.1.md) 或 [macOS 手册](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/FTP-MCP-快速安装手册-macOS-v0.3.1.md) 完成 `setup` 和 `doctor`。macOS 同一个产品包支持 Apple Silicon 和 Intel。Python 必须为 3.12。
2. 安装 Node.js **24.9 以上**及 DSH **0.2.2-rc.1**。本适配只声明该 DSH 版本；升级 DSH 前应重新验证。
3. CLI 用户退出正在运行的目标 profile；以下命令使用 `web`，请按实际名称替换。**桌面版用户使用下方的桌面应用安装步骤，不要把 CLI 命令中的 web 改成 desktop。**

本插件不自动安装 Python、不联网下载运行时，也不改写 Codex / WorkBuddy 的 MCP 配置。配置和系统凭据继续由独立产品管理。

## DeepSeek Harness 桌面版安装

进入桌面应用的插件管理页面，使用“安装插件”的包地址输入功能，填入本机 tarball 的**绝对路径**，例如 `C:/Downloads/dsh-ft-ftp-0.1.0.tgz`，完成安装并启用。该路径应指向本插件包，而非产品离线 zip。也可使用本插件 [GitHub Release](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/releases/tag/dsh-v0.1.0) 中 tarball 的下载链接。

`desktop` profile 由 Electron 应用专属管理，`dsh plugin --profile desktop ...` 会被拒绝。卸载、禁用也通过桌面应用插件管理页面操作。安装后先要求 Agent 调用 `mcp__ft-ftp-mcp-stdio__list_servers`，再做连接测试和目录读取。实际页面文字可能随语言设置变化。

本项目已在 Windows Desktop 0.2.2-rc.1 的实际 Host 内验证热启用、14 个工具注册、现有配置发现、连接及目录读取。macOS 的路径逻辑已有测试，桌面版实机安装和 Keychain 尚未验证。

## 从本地包安装

在项目根目录执行（维护者打包）：

```text
npm pack ./integrations/dsh --pack-destination .
```

将生成的包交给用户。用户进入包所在目录执行：

```text
dsh plugin --profile web add ./dsh-ft-ftp-0.1.0.tgz
dsh --profile web --dump-config
dsh --profile web
```

第二条命令的组合配置中应出现 `id: ft-ftp`、`name: dsh-ft-ftp`。启动后工具名称以 `mcp__ft-ftp-mcp-stdio__` 开头。先调用 `list_servers`，核对服务器别名，再调用 `test_connection`、`list_dir`。能看到配置条目不等于连接成功。

也可从 [GitHub Release](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/releases/tag/dsh-v0.1.0) 下载本地包。npm 发布成功后可使用 `dsh plugin --profile web add dsh-ft-ftp@0.1.0`。市场条目的审核、收录与 npm 发布独立进行，实际状态见 [发布记录](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/DSH-Market-发布记录.md)。

## 路径与参数

默认自动检测产品安装位置：

| 系统 | Python 路径 |
| --- | --- |
| Windows | `%LOCALAPPDATA%\ft-ftp-mcp\venv\Scripts\python.exe` |
| macOS（两种 CPU 相同） | `~/.ft-ftp-mcp/venv/bin/python` |

使用自定义位置时，在启动 DSH 的终端设置 `FT_FTP_MCP_PYTHON` 为解释器**绝对路径**。可选 `FT_FTP_MCP_CONFIG` 指向配置文件绝对路径；未设置时仍使用 `~/.ft-ftp-mcp/config.json`。

Windows PowerShell：

```powershell
$env:FT_FTP_MCP_PYTHON = 'C:\你的安装目录\venv\Scripts\python.exe'
$env:FT_FTP_MCP_CONFIG = 'C:\你的配置目录\config.json'
dsh --profile web
```

macOS 终端：

```sh
export FT_FTP_MCP_PYTHON="$HOME/.ft-ftp-mcp/venv/bin/python"
export FT_FTP_MCP_CONFIG="$HOME/.ft-ftp-mcp/config.json"
dsh --profile web
```

也可通过 DSH 的配置覆盖，在 `id: ft-ftp` 条目下设置 `config.pythonPath`、`config.configPath`、`config.toolCallTimeoutMs`。插件参数优先于环境变量；调用超时默认 120000 毫秒。路径含空格无需额外拼接引号，插件以参数数组启动解释器。

密码、私钥口令仍放系统凭据管理器。若原配置使用 `credential_env`，在启动 DSH 的环境中提供该变量；适配层只向 MCP 子进程显式转发配置引用的凭据变量，避免被官方桥接器的环境清理误删。不要把密码写入 DSH 配置或对话。

## 故障和卸载

- 找不到解释器 / 包版本错误：重新运行产品安装器，或修正 `pythonPath`，然后重启 profile。
- 配置或认证失败：用同一解释器执行 `-m ft_ftp_mcp_stdio doctor`；修改后重启 profile。服务器端只读、路径边界和删除确认规则与独立 MCP 相同。
- MCP 子进程异常退出：官方桥接器最多重连 3 次；失败后修复原因并重启 profile。
- 不要在同一 profile 中另配同名 `ft-ftp-mcp-stdio` 桥接实例，否则工具命名空间冲突。

退出 profile 后卸载：

```text
dsh plugin --profile web remove dsh-ft-ftp
dsh --profile web --dump-config
```

卸载仅移除 DSH 插件依赖与组合配置；独立产品、FTP 配置、系统凭据及 Codex / WorkBuddy 手动安装继续保留。

## 验证与发布

仓库中的 `scripts/verify_dsh.mjs` 使用真实 DSH Cordis、ToolsService 和 MCP 桥接器验证工具注册、调用、重载与清理。执行方法及实际结果见 [适配验证记录](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/blob/main/docs/DSH-Market-适配验证.md)。不需要模型 API Key。

正式上架应先把同一份验证通过的 tarball 发布到 npm，再向 [DSH Market](https://dshplugin.io/) 提交插件条目（维护仓库 `tjsdyy/dshplugin` 的 `plugin-submission` Issue 流程）。npm 可下载、市场审核接纳、市场安装成功是三个不同步骤，必须分别核验。
