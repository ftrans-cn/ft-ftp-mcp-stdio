# FT FTP MCP 验证记录

验证日期：2026-11-17。Python 产品及已发布 npm 包：`ft-ftp-mcp-stdio@0.3.1`。npm 发布及实际 Desktop 从 registry 安装已验证；市场收录尚待审核。

## 范围与环境

npm 包位于 `integrations/dsh`，通过 DSH 官方 MCP 桥接器启动 Python stdio 服务。未修改 FTP/SFTP 核心实现、工具契约、访问策略、安装器、已有 Windows / macOS 产品手册及 Codex / WorkBuddy 模板。

Windows x64，Python 3.12.10，隔离 Node 24.22.3，DSH 及官方 MCP 桥接器 0.2.2-rc.1。新包测试从实际 tarball 加载模块，使用真实 Cordis、ToolsService、原生执行器和 MCP 桥接器；FTP 测试绑定 127.0.0.1 随机端口，使用临时目录和测试凭据。

## 已执行结果

| 验证 | 结果 |
| --- | --- |
| 产品基线 Python 回归 | 170 通过，11 跳过；live 场景未启用 |
| 独立 MCP stdio | 版本 0.3.1，14 个工具，启动成功 |
| 新包配置测试 | 2 项通过；覆盖默认路径、含空格路径、参数优先级、无效运行时和凭据变量精确转发 |
| 新包实际 tarball | 包名 ft-ftp-mcp-stdio，版本 0.3.1；包含 README、LICENSE、package.json、patch、两个 mjs，共 6 个文件 |
| 新包真实 DSH 工具调用 | 全部 14 个工具调用通过，单文件上传下载内容核对及目录传输通过 |
| 权限限制与错误传播 | 只读写入、未确认删除、路径越界均被拒绝并识别为错误 |
| 崩溃恢复 | 终止测试专属 MCP 子进程后，新进程出现，真实连接调用恢复 |
| 禁用、重载、失败清理 | 工具注销、子进程终止；重新加载注册成功；无效运行时不遗留工具 |
| 官方 npm 发布 | registry 返回 0.3.1，dist.integrity 与发布 tarball 一致 |
| 实际 Desktop 从 npm 安装 | 官方 pluginManager 按包名安装，application=applied；依赖及锁文件记录 registry 版本 0.3.1 |
| 安装后实际 Host 调用 | 注册 14 个工具，发现 3 个服务器；list_servers、test_connection、list_dir 均通过；未进行远端写入 |
| 验证清理 | 临时 probe 已移除，原 profile patch 按字节恢复；npm 插件依赖保留 |
| 产品 Windows Desktop 基线 | 实际 Host 中 14 个工具注册、配置发现、默认服务器连接及目录读取通过 |

已发布包的完整性与 SHA-256 见 [发布记录](DSH-Market-发布记录.md)。README 清理不涉及运行代码变化。实际 Desktop 安装使用包名及官方 registry，未使用本地包路径。

## 复测

仓库根目录执行以下 PowerShell 命令，假设 Node >=24.9、npm、uv 和开发 `.venv` 可用：

```powershell
New-Item -ItemType Directory -Force build/dsh-validation, release | Out-Null
npm pack ./integrations/dsh --pack-destination ./release
npm install --prefix build/dsh-validation --no-audit --no-fund @deepseek-ai/dsh@0.2.2-rc.1 ./release/ft-ftp-mcp-stdio-0.3.1.tgz
uv pip install --target build/dsh-validation/python-test-deps pyftpdlib==2.2.0
$env:FT_FTP_TEST_PYTHON = "$PWD\.venv\Scripts\python.exe"
node --test integrations/dsh/test/*.test.mjs
$env:PYTHONPATH = "$PWD\build\dsh-validation\python-test-deps"
node scripts/verify_dsh.mjs build/dsh-validation .venv/Scripts/python.exe
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/verify_offline_install.py 0.3.1
```

`verify_dsh.mjs` 不需要模型 API Key，使用专属临时目录并清理测试进程。断线时可能短暂保留工具 Schema，验证以真实只读调用再次成功为准。不能因连接中断自动重试文件写入。

## 验证边界

- registry 安装已验证；市场目录收录及从市场入口安装仍待后续审核与验证。
- macOS 两种 CPU 的路径逻辑已有测试，实际安装及 Keychain 未实机验证。
- DSH 的真实远端协议测试使用 FTP，SFTP 沿用原产品实现及已有测试，尚未进行 DSH-to-SFTP 实测。
- Codex / WorkBuddy 的配置和安装链路未修改，本轮未重新操作其图形客户端。
- 兼容范围限于 DSH 0.2.2-rc.1。

源码：[FT FTP MCP](https://github.com/ftrans-cn/ft-ftp-mcp-stdio)。正式发布状态见 [发布记录](DSH-Market-发布记录.md)。
