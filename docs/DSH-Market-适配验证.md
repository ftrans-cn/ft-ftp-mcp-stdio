# DSH Market 适配与验证记录

验证日期：2026-11-17。独立产品版本：0.3.1。适配包版本：`dsh-ft-ftp@0.1.0`。

## 改动范围

新增 `integrations/dsh`，以 npm bundle 包装官方 MCP 桥接器，通过参数数组启动独立产品的 Python stdio 入口。没有修改 FTP/SFTP 服务实现、协议契约、权限策略、产品安装器、打包脚本、Codex / WorkBuddy 模板或已有两份安装手册。根 README 只新增适配文档入口。

同一份 DSH tarball 面向 Windows 与 macOS（Apple Silicon / Intel），依赖已经安装的产品运行时。它不包含 Python 或产品 wheel，不替代原来的离线产品包。插件包和产品包分别版本化。

安装时自动选择标准产品路径，支持自定义解释器及配置路径。启动前检查 Python 3.12 和产品 0.3.1，错误不会带出探测的 stdout / stderr。凭据仍使用原产品机制；仅把 FTP 配置实际引用的 `credential_env` 变量显式补回官方桥接器清理后的子进程环境。

## 已执行的验证

环境：Windows x64、Python 3.12.10、隔离 Node 24.22.3、DSH / 官方 MCP 桥接器 0.2.2-rc.1。DSH_HOME 使用 `build/dsh-validation/home`，没有改动日常 DSH profile；FTP 使用临时目录和仅绑定 127.0.0.1 随机端口的测试服务器，没有访问用户已有远端服务器或凭据。

| 验证 | 实际结果 |
| --- | --- |
| 原有 Python 测试 | 170 passed，11 skipped；live 测试未启用 |
| 独立 MCP stdio 启动、版本、工具清单 | 产品版本 0.3.1，14 个工具，passed |
| 适配层自动化检查 | 2 个测试通过，覆盖两平台默认路径、含空格路径、参数优先级、无效解释器、配置路径及凭据变量转发 |
| npm pack | 仅打入 package.json、两个 mjs、patch、README、LICENSE 共 6 个文件；不含测试环境和用户配置 |
| 真实 DSH CLI 安装 tarball | 成功；profile 依赖和 bundle 清单自动加入插件 |
| 真实 DSH CLI 组合配置 | `id: ft-ftp` / `name: dsh-ft-ftp` 正确出现 |
| 真实 DSH CLI 完整 profile 启动 | 测试 overlay 检查到 14 个工具，并经原生工具执行器成功调用 list_servers |
| DSH 原生 ToolsService / 官方桥接器 → Python → 本地 FTP | 全部 14 个工具均真实调用；单文件上传内容核对、下载内容核对和 SHA-256 格式检查通过，目录上传下载通过 |
| 权限与错误传播 | 只读写入、未确认删除、路径越界均被拒绝，并被 DSH 识别为错误 |
| 子进程崩溃恢复 | 终止测试专属 MCP 进程后，新进程出现，14 个工具恢复，真实 test_connection 再次成功 |
| 禁用和重新加载 | 工具全部注销、MCP 子进程终止；重新启用后命名空间释放，14 个工具重新注册 |
| 无效运行时 | 启动失败；无遗留工具注册 |
| 真实 DSH CLI 卸载 | 依赖和 bundle 移除，重新 dump-config 不再包含 dsh-ft-ftp |
| 新增 Python 测试辅助文件 Ruff | passed |

最终 tarball：`release/dsh-ft-ftp-0.1.0.tgz`。

SHA-256：`a801d5a208eace06850a7f133c48141dceca9f9777b1bb8c36ce594148146023`。

断线恢复有连接窗口；官方桥接器在此期间可能仍保留工具 Schema，而实际调用返回 Not connected。验证以真实只读调用再次成功为恢复标准。适配层不自动重试文件写入，避免把结果不确定的操作重复执行。凭据环境变量在插件启动时读取，更新后应重启 profile。

## 复测方法

以下 PowerShell 命令在仓库根目录执行，假设已安装 Node >=24.9、npm、uv，并已有开发用 `.venv`。这是维护者隔离验证环境，不是终端用户安装步骤。

```powershell
New-Item -ItemType Directory -Force build/dsh-validation, release | Out-Null
npm pack ./integrations/dsh --pack-destination ./release
npm install --prefix build/dsh-validation --no-audit --no-fund @deepseek-ai/dsh@0.2.2-rc.1 ./release/dsh-ft-ftp-0.1.0.tgz
uv pip install --target build/dsh-validation/python-test-deps pyftpdlib==2.2.0
$env:FT_FTP_TEST_PYTHON = "$PWD\.venv\Scripts\python.exe"
node --test integrations/dsh/test/*.test.mjs
$env:PYTHONPATH = "$PWD\build\dsh-validation\python-test-deps"
node scripts/verify_dsh.mjs build/dsh-validation .venv/Scripts/python.exe
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe scripts/verify_offline_install.py 0.3.1
```

`verify_dsh.mjs` 从隔离环境加载已安装的 tarball，使用真实 Cordis、SystemPrompt、ToolsService、原生执行器和官方 MCP 桥接器，不使用模拟桥接器，也不需要模型 API Key。它启动本地 FTP fixture，结束时删除临时文件并终止测试进程。断线期间探测调用数可能随机器速度变化，故不把固定调用次数当通过条件。

CLI 安装 / 卸载复测：

```powershell
$env:DSH_HOME = "$PWD\build\dsh-validation\home"
$dshEntry = "$PWD\build\dsh-validation\node_modules\@deepseek-ai\dsh\lib\bin.js"
node $dshEntry plugin --profile ftp-validation add "$PWD\release\dsh-ft-ftp-0.1.0.tgz"
node $dshEntry --profile ftp-validation --dump-config
$env:FT_FTP_MCP_PYTHON = "$PWD\.venv\Scripts\python.exe"
# 使用自己的隔离测试配置，勿把测试操作指向生产服务器。
$env:FT_FTP_MCP_CONFIG = "$PWD\build\dsh-validation\profile-ftp.json"
```

完整 profile 探测的配置与 overlay（只调用服务器发现，不连接远端）：

```powershell
@{version=2; servers=@(@{alias='isolated';protocol='ftp';host='127.0.0.1';port=9;username='unused';root='/';readOnly=$true});default_server='isolated';staging_dir="$PWD\build\dsh-validation\staging";log_usage=$false} |
    ConvertTo-Json -Depth 4 | Set-Content $env:FT_FTP_MCP_CONFIG
$probeUrl = ([uri]"$PWD\scripts\dsh_profile_probe.mjs").AbsoluteUri
@"
- insert:
    - id: ftp-profile-probe
      name: '$probeUrl'
"@ | Set-Content build/dsh-validation/probe.patch.yml
$env:FT_FTP_DSH_PROBE_REPORT = "$PWD\build\dsh-validation\profile-result.json"
node $dshEntry --profile ftp-validation --patch "$PWD\build\dsh-validation\probe.patch.yml"
```

该命令保持运行。在另一个终端检查 `profile-result.json` 包含 `profileBoot: passed`、`toolCount: 14`、`listServers: passed`，然后在原终端 Ctrl+C 退出，执行：

```powershell
node $dshEntry plugin --profile ftp-validation remove dsh-ft-ftp
node $dshEntry --profile ftp-validation --dump-config
```

最后的组合配置必须不包含该插件。实际执行的本机日志位于忽略跟踪的 `build/dsh-validation` 下；可分享的结论保存在本文。

## 验证边界与发布状态

### 本机桌面版安装补充（2026-11-17）

首次验证使用本地构建 tarball（SHA-256：`393459abaed4b16ed07078c112c538de50a376e792c1bbbb61783f792512164d`），安装到本机正在运行的 DeepSeek Harness Desktop 0.2.2-rc.1 的 `desktop` profile，使用正式安装的产品 Python（产品版本 0.3.1），没有使用开发 `.venv`。桌面版 CLI 明确保留 desktop profile，因此实际通过桌面进程自带的 `pluginManager` 服务完成安装与启用，并验证 `application: applied`、无警告。

在当前桌面 Host 内临时加载只读探测插件，经实际 ToolsService 和原生执行器验证：14 个工具注册成功；`list_servers` 识别到现有 3 个服务器；默认服务器 `test_connection` 和根目录 `list_dir` 成功。未执行远端写入，也未把服务器地址、账号、凭据或文件清单写入报告。MCP 子进程的父进程为当前 Desktop Host，证明验证落在实际桌面应用中。

首次从热更新辅助插件内调用管理服务继承了 HMR 事务上下文，导致嵌套事务错误；临时辅助代码脱离该异步上下文后，通过管理服务成功启用。该代码仅用于本机安装，未加入产品 tarball。全部临时探测条目已移除，用户原始 `cordis.patch.yml` 与备份逐字节一致；`package.json` 保留正式插件依赖及 bundle 启用项。应用未重启。

随后仅更新包内安装说明，重新打包得到本文前述最终 SHA-256；从 GitHub Release 下载回最终包并校验一致，全新隔离 profile 下 14 个工具注册和 list_servers 再次通过。最终包的真实 DSH / FTP 全工具验证也已通过。

本机证据及安装前备份位于 `build/dsh-desktop-install-20261117`（忽略跟踪）。这是本地安装，不是 npm 发布或市场上架。

- macOS 两种 CPU 的实际 DSH 安装、Keychain 凭据读取尚未实机执行；路径选择已有测试，不能代替实机验证。
- 本次新增端到端测试使用 FTP；SFTP 复用原产品实现及原有测试，未在 DSH 链路上连接真实 SFTP 服务器。
- Codex / WorkBuddy 的现有安装链路与模板未改动，独立 stdio 验证通过；本次未操作它们的图形客户端重新安装。
- 兼容范围限定 DSH 0.2.2-rc.1，不能据此宣称后续版本已验证。
- 本地可安装不等于市场已上架；当前代码推送、npm 与市场提交状态以 [发布记录](DSH-Market-发布记录.md) 为准。

正式上架使用经过验证的同一 tarball 发布 npm，再验证公开 registry 安装，最后向市场提交条目。应分别记录 npm 版本/完整性、提交 Issue URL、审核结果和市场安装后的真实工具调用；不得把“已提交”标记为“已上架”。适配位于子目录，市场安装指令应使用 npm 包名，不能把当前项目根目录直接当作 DSH bundle 安装。

规则来源：[DSH 官方 bundle 发布与 profile 安装说明](https://github.com/deepseek-ai/deepseek-harness/blob/master/docs/user/develop/basic/publish.md)、[官方 MCP 桥接器说明](https://github.com/deepseek-ai/deepseek-harness/tree/master/packages/mcp/mcp-client)、[DSH Market 提交入口](https://github.com/tjsdyy/dshplugin/issues/new?labels=plugin-submission)。运行行为以此次安装的 npm 0.2.2-rc.1 包和实际测试为准。


### npm 正式包验证补充（2026-11-17）

账号所有者完成发布认证后，官方 registry 的 `dsh-ft-ftp@0.1.0` 已可查询。`dist.integrity` 为 `sha512-7vzCWR+WvV7vzospwW8zs0g0Pk96/7fFfDu0KW48Kwog3fcH0GmFpOX2/8Hxaz+TMvH6K0X/64hAz65UiTHlrQ==`，下载后 SHA-256 与最终 Release 包一致。发布初期遇到短暂 CDN 404 缓存，缓存过期后在全新隔离 `ftp-npm-validation` profile 执行 `dsh plugin --profile ftp-npm-validation add dsh-ft-ftp@0.1.0 --registry https://registry.npmjs.org/` 成功，随后真实启动 profile，14 个工具注册和 list_servers 调用通过。该检查不修改用户日常 desktop profile。
