# FTP MCP 0.3.1 快速安装手册

> 本文档是 ft-ftp-mcp-stdio-0.3.1（以下简称"本工具"）的快速安装手册。

1. 安装 Python 3.12 x64（本机如已安装则忽略本步骤）
   下载地址：<https://www.python.org/ftp/python/3.13.12/python-3.13.12-amd64.exe/>，下载 Windows installer (64-bit) 安装包，安装时勾选 "Add python.exe to PATH"。

2. 解压本工具的安装包
   `ft-ftp-mcp-stdio-offline-0.3.1-py312-win64.zip` → `D:\ft-ftp-mcp-stdio-0.3.1`（示例路径）

   解压后目录中应能看到 `install.bat`、`VERSION.txt`、`wheels`、`templates` 等文件或目录。

3. 在 Windows PowerShell 中执行安装

   ```powershell
   cd D:\ft-ftp-mcp-stdio-0.3.1
   .\install.bat
   ```

   安装成功后，系统提示 Installation complete，以及相关辅助信息。

   可选校验版本：

   ```powershell
   & "$env:LOCALAPPDATA\ft-ftp-mcp\venv\Scripts\python.exe" -c "import importlib.metadata; print(importlib.metadata.version('ft-ftp-mcp-stdio'))"
   ```

   预期输出：

   ```text
   0.3.1
   ```

4. 将本工具注册到 AI 应用（WorkBuddy、Codex）
   如果当前只是手动安装和配置服务器，可跳过本步骤，直接进入第 5 步。

   install.bat 结束时提示模板位置 `Generated client templates: ...\AppData\Local\ft-ftp-mcp\templates`，该目录中已存有两份本机真实配置片段（workbuddy-mcp.json 和 codex-config.toml）。

   **WorkBuddy**

   - 把 `templates\workbuddy-mcp.json` 中 `mcpServers` 下的 `ft-ftp-mcp-stdio` 条目，复制进 WorkBuddy 配置文件（通常是 `C:\Users\用户名\.workbuddy\mcp.json`）的 `mcpServers` 对象里 → 保存配置文件
   - 请注意检查格式：如果原有其他 MCP 服务配置，不同 MCP 服务条目之间用英文逗号分隔，最后一个条目后不加逗号
   - WorkBuddy → 连接器 → 自定义连接器，对新增的 ft-ftp-mcp-stdio 点"信任"
   - 完全退出并重启 WorkBuddy

   **Codex**

   - 把 `templates\codex-config.toml` 中 `mcp_servers.ft-ftp-mcp-stdio` 相关段落，粘贴到 Codex 配置文件（通常是 `C:\Users\用户名\.codex\config.toml`）末尾 → 保存配置文件
   - 完全退出并重启 Codex
   - 开始调用本 MCP 工具时，Codex 会弹出审批窗口（"Allow the ft-ftp-mcp-stdio MCP server to run tool ..."），点**始终允许**即可（作用类似 WorkBuddy 的"信任"）

5. 配置 FTP/SFTP 服务器信息
   在 Windows PowerShell 中执行配置向导：

   ```powershell
   & "$env:LOCALAPPDATA\ft-ftp-mcp\venv\Scripts\python.exe" -m ft_ftp_mcp_stdio setup
   ```

   > 0.3.1 配置为 v2：`root` 必填，`readOnly` 默认 `y`（只读），新增 `description` 字段；0.2.2 中的"批量总大小上限"和"批量文件数上限"不再作为配置字段出现。

   以 FTP 服务器（127.0.0.1:21），命名为 ftp1 为例，向导交互实录：

   ```text
   请选择: 1（添加服务器）
   别名（1-64 位，支持中英文、数字、点、短横线和下划线）（b 返回上一步）: ftp1
   协议 ftp/sftp [ftp]（b 返回上一步）: ftp
   服务器地址（b 返回上一步）: 127.0.0.1
   端口 [21]（b 返回上一步）: 21
   用户名（b 返回上一步）: username
   root [/]（b 返回上一步）: /（或填写受控目录，如 /reports）
   description（可选，勿填写敏感信息）（b 返回上一步）: 本地测试 FTP
   readOnly y/n [y]（b 返回上一步）: n（只读开关慎重选择；需要上传/删除等写操作才设为 n）
   文件名编码 auto/utf-8/gbk [auto]（b 返回上一步）: （回车按默认值）
   单文件上传上限（字节） [2147483648]（b 返回上一步）: （回车按默认值）
   密码或私钥口令（修改时留空保留现值）（b 返回上一步）: （输入密码）
   服务器 ftp1 已保存并通过连接测试。
   ```

   以 SFTP 服务器（127.0.0.1:22/带口令私钥），命名为 sftp-key-pass 为例，向导交互实录：

   ```text
   请选择: 1（添加服务器）
   别名（1-64 位，支持中英文、数字、点、短横线和下划线）（b 返回上一步）: sftp-key-pass
   协议 ftp/sftp [ftp]（b 返回上一步）: sftp
   服务器地址（b 返回上一步）: 127.0.0.1
   端口 [22]（b 返回上一步）: 22
   用户名（b 返回上一步）: username
   root [/]（b 返回上一步）: /（或填写受控目录，如 /hold-root）
   description（可选，勿填写敏感信息）（b 返回上一步）: 本地测试 SFTP
   readOnly y/n [y]（b 返回上一步）: y（只读开关慎重选择）
   文件名编码 auto/utf-8/gbk [auto]（b 返回上一步）: （回车按默认值）
   单文件上传上限（字节） [2147483648]（b 返回上一步）: （回车按默认值）
   私钥路径（留空使用密码）（b 返回上一步）: D:\.ssh\ft-sftp-test-ed25519-pass（示例路径，使用密码则留空直接回车）
   主机指纹（留空使用 TOFU）（b 返回上一步）: （回车按默认值；敏感环境建议填写管理员提供的 SHA-256 指纹）
   密码或私钥口令（修改时留空保留现值）（b 返回上一步）: （输入 SFTP 密码或私钥口令，使用密钥且密钥无密码则直接回车）
   服务器 sftp-key-pass 已保存并通过连接测试。
   ```

   配置完成后，可执行只读诊断：

   ```powershell
   & "$env:LOCALAPPDATA\ft-ftp-mcp\venv\Scripts\python.exe" -m ft_ftp_mcp_stdio doctor
   ```

   只诊断指定服务器：

   ```powershell
   & "$env:LOCALAPPDATA\ft-ftp-mcp\venv\Scripts\python.exe" -m ft_ftp_mcp_stdio doctor --server ftp1
   ```

6. 冒烟测试
   如果已完成第 4 步并重启 Agent，可向 Agent 对话发送提示词，例如：

   ```text
   使用 MCP 工具连接 ftp1，列出根目录内容
   ```

   ```text
   列出 ft-ftp-mcp-stdio 提供的所有工具
   ```

   0.3.1 应能发现 14 个工具：

   ```text
   list_servers, test_connection, list_dir, search_files, get_file_info,
   read_text_preview, download_file, upload_file, make_dir, download_dir,
   upload_dir, rename, move, delete
   ```

   如果当前未接入 AI Agent，可使用第 5 步中的 `doctor` 作为手动安装冒烟验证。`doctor` 通过表示本机安装、配置、凭据和协议登录链路可用。

7. 测试通过后，即可在对话中使用自然语言，让你的 Agent 调用 FTP/SFTP 工具了。

   如果当前不接入 AI Agent，则安装结果到此为止：你已经完成本机安装、服务器配置、凭据保存和连接诊断。注意：`list_dir`、`download_file`、`upload_file`、`delete` 等是 MCP 工具，不是普通命令行子命令，不能仅通过 CLI 直接执行。
