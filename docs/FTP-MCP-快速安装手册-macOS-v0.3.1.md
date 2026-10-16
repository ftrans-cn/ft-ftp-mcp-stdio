# FTP MCP 0.3.1 快速安装手册（macOS 通用版）

> 本文档是 ft-ftp-mcp-stdio-0.3.1（以下简称"本工具"）的快速安装手册，适用于将本工具接入 WorkBuddy 或 Codex 后，通过 AI Agent 使用 FTP/SFTP 能力。

适用范围：**macOS 11 或更新系统，Apple Silicon（M 系列）和 Intel Mac，Python 3.12.x**。同一个安装包同时支持 arm64 与 x86_64，由脚本根据 Python 实际运行架构自动选择依赖。这里的 x86_64 是 64 位，不支持 32 位 x86。

## 1. 安装 Python 3.12

本机如已安装 Python 3.12 且架构正确，可跳过安装。Python 不包含在本工具的离线包中，需要预先安装；不能用 Python 3.13 或更高版本替代。

可从 [Python 3.12.10 官方发布页](https://www.python.org/downloads/release/python-31210/) 的 Files 区域下载 **macOS 64-bit universal2 installer**，双击 `.pkg` 按提示安装。该链接是提供 3.12 系列 macOS 安装器的示例，不表示最新的 3.12 补丁版本。

打开“终端”（Terminal），检查版本和实际运行架构：

```bash
python3.12 --version
python3.12 -c 'import platform; print(platform.machine())'
```

版本应输出 `Python 3.12.x`。Apple Silicon 原生运行时架构应为 `arm64`，Intel Mac 应为 `x86_64`；两种结果均受此包支持。

Apple Silicon 若通过 Rosetta 使用 x86_64 Python，脚本会提示并安装 x86_64 依赖。建议使用原生 arm64 Python。Python 的 universal2 安装器同样支持两种架构，无需分开下载。

## 2. 解压本工具安装包

安装包名称：

```text
ft-ftp-mcp-stdio-offline-0.3.1-py312-macos.zip
```

双击 ZIP 解压，例如放到 `~/Downloads/ft-ftp-mcp-stdio-0.3.1`。后续命令中的解压路径以实际目录为准。

目录中应能看到 `install.sh`、`VERSION.txt`、`requirements-arm64.txt`、`requirements-x86_64.txt`、`SHA256SUMS.txt`、`wheels`、`templates` 和本手册 等文件或目录。请完整解压，不要仅复制安装脚本。

## 3. 在 macOS 终端中执行安装

```bash
cd "$HOME/Downloads/ft-ftp-mcp-stdio-0.3.1"
bash install.sh
```

脚本会检查系统、Python 版本与架构，自动校验包内文件的 SHA-256；校验失败时停止安装。然后在 `~/.ft-ftp-mcp/venv` 创建独立虚拟环境，从包内 `wheels` 离线安装本工具及依赖，并生成 MCP 配置模板。安装依赖不访问 PyPI。

开始安装时会显示 `Selected Python architecture: arm64` 或 `x86_64`，无需手动选择依赖。共用依赖仅保存一份，安装时仅使用共用目录和选中架构目录。

成功后会显示 `Installed. MCP templates: ...`，以及配置和诊断命令。不要使用 `sudo` 执行本工具的安装、配置或启动命令，确保它们与 AI 应用使用同一 macOS 用户。

如果 `python3.12` 不在 PATH，可指定已安装 Python 的完整路径：

```bash
FT_FTP_MCP_PYTHON="/你的Python路径/python3.12" bash install.sh
```

可选校验版本：

```bash
"$HOME/.ft-ftp-mcp/venv/bin/python" -c "import importlib.metadata; print(importlib.metadata.version('ft-ftp-mcp-stdio'))"
```

预期输出 `0.3.1`。

## 4. 将本工具注册到 AI 应用

安装脚本生成的本机配置片段位于：

```text
~/.ft-ftp-mcp/templates/workbuddy-mcp.json
~/.ft-ftp-mcp/templates/codex-config.toml
```

在 Finder 中可按 `Command + Shift + G`，输入目录或配置文件路径，访问以点开头的隐藏目录。编辑 JSON/TOML 时使用纯文本编辑器，不要保存为富文本格式。

模板的 `command` 已是本机 Python 绝对路径，例如 `/Users/用户名/.ft-ftp-mcp/venv/bin/python`；`args` 为 `["-m", "ft_ftp_mcp_stdio"]`。不要复制 Windows 模板中的 `Scripts/python.exe` 路径，也不要将 `command` 改成包含 `~` 的缩写路径。

### WorkBuddy

1. 打开生成的 `~/.ft-ftp-mcp/templates/workbuddy-mcp.json`。
2. 将其中 `mcpServers` 下的 `ft-ftp-mcp-stdio` 条目，复制到 WorkBuddy 实际配置文件的 `mcpServers` 对象里。按原手册的用户目录约定，路径通常是 `~/.workbuddy/mcp.json`；以客户端实际配置位置为准。
3. 保留其他 MCP 服务。不同服务条目之间用英文逗号分隔，最后一个条目后不加逗号；不要将模板中的整个 `mcpServers` 对象嵌套到另一个 `mcpServers` 中。
4. 在“连接器 → 自定义连接器”中，对新增服务按界面提示点“信任”。菜单名称以当前客户端为准；后续 command、args 或 env 变更时，按提示重新信任。
5. 完全退出并重启 WorkBuddy。

### Codex

1. 打开生成的 `~/.ft-ftp-mcp/templates/codex-config.toml`。
2. 将 `mcp_servers.ft-ftp-mcp-stdio` 及其 `.env` 段落合并到 `~/.codex/config.toml`。如果已有同名段落，更新原段落，不要重复添加；保留其他配置。
3. 完全退出并重启 Codex。
4. 若客户端要求授权，按实际提示处理。审批方式受客户端版本和组织策略影响，不保证固定出现“始终允许”选项。

配置路径与 stdio 参数说明可参见 [OpenAI 官方 MCP 文档](https://developers.openai.com/codex/mcp)。

## 5. 配置 FTP/SFTP 服务器信息

在 macOS 终端中执行配置向导：

```bash
"$HOME/.ft-ftp-mcp/venv/bin/python" -m ft_ftp_mcp_stdio setup
```

0.3.1 使用 v2 配置：`root` 必填，`readOnly` 默认 `y`（只读），支持 `description` 字段；0.2.2 的“批量总大小上限”和“批量文件数上限”不再是配置字段。

密码和私钥口令默认保存到 macOS 钥匙串（Keychain），不写入 `config.json`。首次保存或读取时，若系统请求钥匙串访问授权，请核对访问程序后按提示处理。

下面的 `127.0.0.1` 仅用于当前 Mac 确实运行了 FTP/SFTP 服务的演示。若服务在其他电脑上，请填写真实地址、端口和账号。交互示例中括号里的说明不是实际输入内容。

### FTP 示例

以 FTP 服务器 `127.0.0.1:21`、别名 `ftp1` 为例，向导填写示例：

```text
请选择: 1（添加服务器）
别名（1-64 位，支持中英文、数字、点、短横线和下划线）（b 返回上一步）: ftp1
协议 ftp/sftp [ftp]（b 返回上一步）: ftp
服务器地址（b 返回上一步）: 127.0.0.1
端口 [21]（b 返回上一步）: 21
用户名（b 返回上一步）: username
root [/]（b 返回上一步）: /（或受控目录，如 /reports）
description（可选，勿填写敏感信息）（b 返回上一步）: 本地测试 FTP
readOnly y/n [y]（b 返回上一步）: y（需要上传/删除等写操作时才设为 n）
文件名编码 auto/utf-8/gbk [auto]（b 返回上一步）: （回车按默认值）
单文件上传上限（字节） [2147483648]（b 返回上一步）: （回车按默认值）
密码或私钥口令（修改时留空保留现值）（b 返回上一步）: （输入密码）
服务器 ftp1 已保存并通过连接测试。
```

### SFTP 示例

以 SFTP 服务器 `127.0.0.1:22`、带口令私钥、别名 `sftp-key-pass` 为例：

```text
请选择: 1（添加服务器）
别名（1-64 位，支持中英文、数字、点、短横线和下划线）（b 返回上一步）: sftp-key-pass
协议 ftp/sftp [ftp]（b 返回上一步）: sftp
服务器地址（b 返回上一步）: 127.0.0.1
端口 [22]（b 返回上一步）: 22
用户名（b 返回上一步）: username
root [/]（b 返回上一步）: /（或受控目录，如 /hold-root）
description（可选，勿填写敏感信息）（b 返回上一步）: 本地测试 SFTP
readOnly y/n [y]（b 返回上一步）: y
文件名编码 auto/utf-8/gbk [auto]（b 返回上一步）: （回车按默认值）
单文件上传上限（字节） [2147483648]（b 返回上一步）: （回车按默认值）
私钥路径（留空使用密码）（b 返回上一步）: /Users/用户名/.ssh/ft-sftp-test-ed25519-pass（替换为实际路径，使用密码则留空）
主机指纹（留空使用 TOFU）（b 返回上一步）: （回车按默认值；敏感环境建议填写管理员提供的 SHA-256 指纹）
密码或私钥口令（修改时留空保留现值）（b 返回上一步）: （输入密码或私钥口令，使用无口令密钥时直接回车）
服务器 sftp-key-pass 已保存并通过连接测试。
```

本地配置文件位于 `~/.ft-ftp-mcp/config.json`，下载默认暂存到 `~/.ft-ftp-mcp/staging/`。SFTP 私钥路径填写当前 Mac 上的真实文件路径；远端 `root` 始终使用 `/` 风格的服务器目录，两者不要混淆。

配置完成后，执行只读诊断：

```bash
"$HOME/.ft-ftp-mcp/venv/bin/python" -m ft_ftp_mcp_stdio doctor
```

只诊断指定服务器：

```bash
"$HOME/.ft-ftp-mcp/venv/bin/python" -m ft_ftp_mcp_stdio doctor --server ftp1
```

## 6. 冒烟测试

完成第 4、5 步并重启 AI 应用后，向 Agent 发送：

```text
使用 ft-ftp-mcp-stdio 列出已配置的服务器，然后测试 ftp1 的连接并列出根目录内容。
```

再发送：

```text
列出 ft-ftp-mcp-stdio 提供的所有工具。
```

0.3.1 应能发现 14 个工具：

```text
list_servers, test_connection, list_dir, search_files, get_file_info,
read_text_preview, download_file, upload_file, make_dir, download_dir,
upload_dir, rename, move, delete
```

## 7. 开始使用

测试通过后，即可用自然语言让 Agent 调用 FTP/SFTP 工具。涉及 Mac 上的本地文件时，请使用 Mac 绝对路径，如 `/Users/用户名/Downloads/report.csv`；远端文件仍使用 `/reports/report.csv` 这样的虚拟绝对路径。

## 常见问题

| 现象 | 处理方式 |
| --- | --- |
| `python3.12: command not found` | 确认安装的是 Python 3.12，重新打开终端，或用 `FT_FTP_MCP_PYTHON` 指定完整路径。 |
| 提示 `Python 3.12.x is required` | 指向 Python 3.12 解释器，不能用 3.13 或更高版本替代。 |
| 提示 Rosetta | 可继续使用 x86_64 依赖；如需原生运行，请改用 arm64 Python，已有不同架构虚拟环境需先重命名备份。 |
| 提示不支持的 Python 架构 | 当前仅支持 arm64 和 x86_64；请核对解释器及系统架构。 |
| 现有虚拟环境版本或架构不匹配 | 退出 AI 应用并备份配置；仅将 `~/.ft-ftp-mcp/venv` 重命名后重新安装，不要删除整个 `~/.ft-ftp-mcp` 目录。 |
| SHA-256 校验失败 | 重新获取并解压完整安装包，不要跳过校验。 |
| Agent 找不到 MCP 服务 | 检查模板是否合并到客户端实际配置、Python 绝对路径是否存在，完成信任并完全重启客户端。 |
| 钥匙串读取失败 | 用安装后的同一个 Python 和同一 macOS 用户执行 setup/doctor，并按系统提示处理钥匙串授权。 |
| 连接 127.0.0.1 失败 | 该地址表示当前 Mac；若 FTP/SFTP 服务在其他机器上，请填写真实服务器地址。 |
| 能列目录但不能上传或删除 | 检查 readOnly 是否为只读，并确认远端账号权限和客户端授权。 |


## 依赖版本说明

安装脚本自动选择以下依赖，无需用户手动修改：

| Python 运行架构 | 依赖清单 | cryptography 版本 |
| --- | --- | --- |
| arm64 | requirements-arm64.txt | 50.0.1 |
| x86_64 | requirements-x86_64.txt | 48.0.1 |

Intel 使用兼容版本是因为 cryptography 从 49 起移除了 Intel macOS 支持。
实际依赖版本与哈希在上述清单中，Intel 兼容锁在 `compatibility-lock-x86_64.txt`，
构建信息在 `BUILD-INFO.json`。不要自行升级或混用两种架构的依赖。
