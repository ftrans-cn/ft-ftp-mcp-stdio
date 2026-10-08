# ft-ftp-mcp-stdio v0.3.1

- 发布日期：2026-09-29
- 发布状态：发布候选已重新构建并通过技术验证；快速安装手册下载链接待校正后正式发布
- 分发形态：Windows 10/11 x64、Python 3.12 的离线全量 ZIP；不单独发布 wheel 或 sdist
- 安装包名称：`ft-ftp-mcp-stdio-offline-0.3.1-py312-win64.zip`

## 主要变化

- 简化交互式配置流程：不再询问凭据环境变量，新配置统一将密码或私钥口令保存到操作系统钥匙串；已有配置中的 `credential_env` 继续兼容。
- 服务器别名支持中文、英文、数字、点、短横线和下划线，长度为 1 至 64 位，并在命令行输入时直接提示规则。
- 保存服务器配置后不再自动打印 Codex 和 WorkBuddy 配置模板；仍可通过配置向导菜单按需查看。
- 离线发布包自动选择版本号最高的 `FTP-MCP-快速安装手册-v*.md`，不再包含旧的 `用户手册_v1.12.md`。

## 兼容性

配置文件版本仍为 v2，MCP 工具契约和 14 个工具保持不变。本次只调整配置向导交互、别名校验和离线包手册选择逻辑。

## 验证状态

非 live 全量回归为 `164 passed, 11 skipped`，Ruff 和 mypy 通过。离线构建生成 73 个 wheel、总计 22,901,226 字节；ZIP 包含 79 个文件、大小 22,508,581 字节，SHA-256 为 `5A4289F7647DB106BB6EE843D849D997C50BC73B95120CB11FC161D110E392C1`。隔离目录中的首次离线安装、模板生成、安装元数据版本、stdio 初始化、MCP Server 版本及精确 14 工具发现均通过。发布包选择 `FTP-MCP-快速安装手册-v0.3.1.md`，未包含旧的 `用户手册_v1.12.md`。

---

# ft-ftp-mcp-stdio v0.3.0

- 发布日期：2026-09-23
- 发布状态：已批准正式发布并完成本地 Git 归档；尚未推送或正式分发
- Git 标签：`v0.3.0`（annotated tag）
- 分发形态：Windows 10/11 x64、Python 3.12 的离线全量 ZIP；不单独发布 wheel 或 sdist
- 安装包名称：`ft-ftp-mcp-stdio-offline-0.3.0-py312-win64.zip`

## 主要变化

- MCP 工具从 13 个增加到 14 个，新增不连接远端、不读取凭据的 `list_servers`。
- 配置契约升级为 v2：`root` 必填、`readOnly` 默认 `true`，支持服务器 `description`；不自动迁移或覆盖 v1 配置。
- 14 个工具提供完整 title、description、封闭输入/输出 Schema 和准确 annotations；业务错误以 `isError=true` 返回稳定结构。
- 远端路径统一为相对于配置 root 的虚拟绝对路径，工具结果和错误不暴露真实 root、连接或凭据信息。
- SFTP 在认证前执行配置指纹或 known-hosts/TOFU 校验，known-hosts 使用跨进程互斥和原子持久化。
- 本地上传拒绝 symlink、junction 和 reparse point；SFTP 逐段拒绝远端链接，FTP 保留协议能力边界。
- 上传执行逐文件大小限制、同目录临时对象和安全提交；写操作响应不确定时不盲目重放，并返回 `outcome_unknown`。
- 批量结果增加 `status`、逐项 `failed`/`skipped`，`upload_dir` 另有 `indeterminate`；调用方不得整体重试不确定批次。
- 文本预览、FTP/SFTP `mtime`、下载完整性检查、setup 默认值与客户端注册名得到统一修正。

## 兼容性与迁移

本版本包含公共 MCP 契约和配置格式变化，属于 `0.x` 阶段的 MINOR 升级。配置 v1 不受支持，也不提供自动迁移工具。若默认位置已存在 v1 配置，必须先人工备份并显式替换或删除，再运行 `ft-ftp-mcp-stdio setup` 创建 v2 配置。正式宿主配置继续使用注册名 `ft-ftp-mcp-stdio` 和已安装虚拟环境中的 `python -m ft_ftp_mcp_stdio`。

## 验证状态

实现 Candidate `0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1` 已通过独立代码复审。发布准备阶段的非 live 回归为 `154 passed, 11 skipped`；Ruff、mypy、FastMCP 五项能力探针及运行时 Schema 比较均通过。10 项 live 测试因未传 `--live` 跳过，另 1 项因 Windows 创建文件 symlink 返回 `WinError 1314` 跳过；junction、reparse 属性和句柄身份边界已有实际覆盖。

发布 Release Candidate 为 `a6431909bdc82e9aec1070fc6635ddaa27dd186a`。独立发布复审的首轮文档 findings 经两次聚焦增量复审全部关闭，最终 P0/P1/P2/P3 均为 0，允许进入最终构建与隔离安装验收。完整记录见 `docs/development/reviews/0.3.0-release-review.md`。

最终构建生成 73 个 wheel、总计 22,893,464 字节；离线 ZIP 包含 79 个文件、大小 22,499,801 字节，SHA-256 为 `1DA54E59D8EA13F452BCA548E05268C8B0AD52C42D7A88E6DBD703AA3CC0C737`。在新的隔离目录中重定向 `LOCALAPPDATA` 并强制 `PIP_NO_INDEX=1` 后，首次安装、重复安装、两份宿主模板解析、安装元数据版本、真实 stdio 初始化、MCP server version 及精确 14 工具 `tools/list` 均通过。该产物来自已审查 Candidate；复审归档提交不改变发布包输入。

P2 根目录修复完全位于远端 driver 创建前的本地预检，版本化和构建脚本调整不改变 FTP/SFTP 行为，因此本阶段不重复执行 live 写入矩阵，沿用实现 Candidate 已通过的 `159 passed, 1 skipped` live 证据。版本 `0.3.0` 已批准正式发布并以本地 annotated tag `v0.3.0` 归档；当前仓库没有远端，产物尚未推送或正式分发。

若发布后发现需要撤回的问题，不改写 `v0.3.0` 标签或 Git 历史；应记录影响和处置，停止使用尚未分发的产物，并通过后续修复版本提供替代。

## 已知边界

继续保留已接受的风险和非目标：WorkBuddy 模型侧 annotations 不可见；FTP 无法可靠识别所有 symlink；SFTP 与本地逐段检查后仍存在 TOCTOU；首次目标检查后的并发覆盖和临时名称竞态按 ADR 0007 接受；本地上传没有允许根白名单；下载和批量调用没有客户端总量限制；staging 没有 TTL、配额或自动清理；不支持 FTPS、断点续传、异步传输或事务式批量回滚。

---

# ft-ftp-mcp-stdio v0.2.2

- 发布日期：2026-09-12
- 发布状态：已发布
- 分发形态：Windows x64 离线全量安装包（自研 wheel + 全部依赖 wheels + `install.bat` + 接入模板 + 用户手册 v1.11 + 包内 SHA-256 清单），不再提供 PyInstaller exe。
- 运行前提：本机预装 64 位 Python 3.12.x；3.11/3.13 不支持。macOS/Linux 离线包留待后续版本。
- 安装方式：解压后运行 `install.bat`，从包内 wheels 离线安装到 `%LOCALAPPDATA%\ft-ftp-mcp\venv`；安装器生成含该 venv Python 绝对路径的 WorkBuddy/Codex 接入模板。先接入 Agent，再配置 FTP/SFTP 服务器。
- 本次仅更换部署形态；MCP stdio 入口和 13 个工具保持不变。delete 的强制人工确认、传输超时/异步及 staging 自动清理仍为后续事项。

## 验证结果

- pytest：`122 passed`（Python 3.12.13，完整 `--live`，含真实 FTP/SFTP）。
- ruff、mypy：通过。
- 离线安装：解压 zip 全新目录安装、重复安装（幂等）、生成模板 JSON/TOML 解析校验、13 工具 stdio 握手均通过。
- 离线包：`ft-ftp-mcp-stdio-offline-0.2.2-py312-win64.zip`，22,499,787 字节，78 文件，SHA-256 `BB288A3AED07B9931BCA168CA41EF5317C2A2598B2A1C04B67D2B2950214FECB`。

---

# ft-ftp-mcp-stdio v0.2.1

- 发布日期：2026-09-11
- 发布状态：已发布
- 分发形态：Python wheel/sdist + Windows x64 单文件 exe

## 热修内容

- 修正 setup 客户端配置片段：PyInstaller exe 使用空 `args`，Python 安装形态继续使用 `-m ft_ftp_mcp_stdio`。
- Codex TOML 增加 env 小节；Codex 与 JSON 片段统一设置 `FASTMCP_SHOW_SERVER_BANNER=false` 和 `PYTHONUTF8=1`。
- WorkBuddy 检测路径修正为 `~/.workbuddy/mcp.json`，片段服务器名统一为 `ft-ftp-mcp`。
- setup 菜单新增“7. 列出服务器”，纯本地显示服务器配置、凭据方式与默认服务器，不连接网络、不读取钥匙串。
- server 入口增加 argv 防呆：无效参数打印参数值和正确用法，并以退出码 2 结束；正常 CLI 子命令和无参数 stdio 启动保持不变。

## 范围说明

- delete 硬确认、传输超时/异步传输、staging 自动清理顺延至 0.2.2，本版不包含。

## 验证结果

- pytest：`121 passed`（完整 `--live`，含 FTP/SFTP 密码与两类 SFTP 私钥）。
- ruff、mypy：通过。
- exe MCP：无参数 stdio 握手成功，13 个工具注册并完成真实 `test_connection(ftp1)` 调用。
- exe setup：菜单 5 输出空 args、双 env 与统一服务器名；菜单 7 正确列出本地服务器配置。
- wheel：元数据版本为 `0.2.1`；sdist 未嵌入已有构建或发布产物。

## 产物 SHA-256

- `ft-ftp-mcp-stdio.exe`: `C9123F1A4C11A48F4A1F73F60E28029DBCAF63CB67B070233B62284271B487CA`
- `ft_ftp_mcp_stdio-0.2.1-py3-none-any.whl`: `DE319E53D84FAA2D972FCD984B83DA095D32A6F0D2CBFE17CC94752117F16631`
- `ft_ftp_mcp_stdio-0.2.1.tar.gz`: `B9A8AF56D9959DA5DE2DC7D65C4640A087776AC056FE341CFD375C609DAA6B0F`

---

# ft-ftp-mcp-stdio v0.2.0 发布候选

- 候选构建日期：2026-09-11
- 发布状态：已发布
- 发布日期：2026-09-11
- 分发形态：Python wheel/sdist + Windows x64 单文件 exe

## 本批完成

- SFTP 密码、无口令 ed25519 私钥、keyring 注入口令的 ed25519 私钥三种真实登录链路纳入 `--live`。
- Windows x64 单文件 exe 支持 stdio server 与 `cred`、`setup`、`doctor`；exe 冒烟确认 13 工具、真实 FTP MCP 调用与 JSONL 落盘。
- 新增默认开启的 JSONL 使用日志：按日写入 `~/.ft-ftp-mcp/logs/usage-YYYYMMDD.jsonl`，仅记录时间、工具、服务器别名、路径、状态和耗时，不含凭据或文件内容。
- `doctor` 增加日志目录只读可写性检查；配置规范新增顶层 `log_usage`，可设为 `false` 关闭。
- JSONL 按本机日期分文件；服务端每次工具调用只写一条。若同一用户动作出现时间不同的两条记录，表示客户端/Agent 实际发送了两次 MCP 调用（重试或重复规划），并非日志重复写入。

## 验证结果

- pytest：`113 passed`（完整 `--live`，含 FTP/SFTP 密码与两类 SFTP 私钥）。
- ruff、mypy：通过。
- exe CLI：`cred list`、`setup`、`doctor` 通过；doctor 全项 PASS。
- exe MCP：stdio 启动、13 工具注册、`test_connection(ftp1)` 真实调用、单条 JSONL 日志通过。
- wheel：隔离安装后版本 `0.2.0`、13 工具注册通过。
- Windows Defender：Antivirus/Real-time Protection 均开启；对最终 exe 执行 `Start-MpScan -ScanType CustomScan`，扫描前后威胁记录均为 1，未新增检测。现有记录是 2023 年其他 NAS 软件备份的历史已处置项，与本产物无关。

## 产物 SHA-256

- `ft_ftp_mcp_stdio-0.2.0-py3-none-any.whl`: `C3EC8341B69873AC79689B1759B5AB29511D8E06B5E0B348289DD182AC173787`
- `ft_ftp_mcp_stdio-0.2.0.tar.gz`: `59E4B89A5BD6EB2D43722630F5496BA18EFBE0E1602A38A62F92654AE631A536`
- `ft-ftp-mcp-stdio.exe`: `3BB9CC25F8D886ECFDDBAF0AEC05F4D1B8F2BC724C7C388B81208FF4DB8F5D14`

## 发布后跟进

- 兼容矩阵：ProFTPD、FileZilla Server、IIS、OpenSSH 正式覆盖、NAT/防火墙被动模式及国内主流客户端选测。
- 企业杀毒：在目标企业环境中复制 exe，更新病毒库后执行落盘扫描、启动扫描、stdio/MCP 冒烟；PyInstaller 单文件自解压可能触发启发式误报，发生时保留引擎名称、规则编号、产物 SHA-256 并走企业白名单/送检流程，禁止关闭防护规避。
- Claude Desktop：本机未安装，配置接入与 13 工具正式冒烟延后。
- QA_NAS：`/mcp_test_20260910_140838`、`/mcp_ftp_rw_20260910_141029`、`/mcp_sftp_rw_20260910_141029` 仍由 QA 复测时清理。

## 不在本版范围

- FTPS、断点续传、GUI、多用户或远程服务模式。

---

# ft-ftp-mcp-stdio 内测版 v0.1

- Python 包版本：`0.1.0`
- 发布日期：2026-09-05
- 发布范围：内部测试

## 本版功能

- 通过 stdio MCP Server 连接 FTP 或 SFTP 服务器，不监听本机网络端口。
- 提供 7 个工具：连接测试、列目录、递归搜索、查看文件信息、下载文件、上传文件和创建目录。
- 每次工具调用独立建立并关闭 FTP/SFTP 连接，连接失败时自动重试一次。
- 支持多服务器配置，可通过服务器别名选择目标服务器。
- 支持服务器根目录限制、只读模式、下载大小上限和上传覆盖确认。
- 下载文件写入本机暂存目录，并返回本地路径与 SHA-256 校验值。
- 密码或私钥口令从操作系统凭据管理器或指定环境变量读取，不写入配置文件。
- SFTP 支持私钥认证和服务器主机密钥校验。

## 配置说明

发布包中的 `config.example.json` 是不含真实服务器信息和凭据的完整字段模板。使用时将其复制为：

`%USERPROFILE%\.ft-ftp-mcp\config.json`

然后替换服务器地址、用户名、根目录等占位内容。密码不要写入 JSON；请使用 `ft-ftp-mcp-stdio cred add <服务器别名>` 存入操作系统凭据管理器，或通过 `credential_env` 指定密码环境变量。

## 已知限制

- 当前只支持 FTP 和 SFTP，不支持 FTPS。
- 当前仅提供上述 7 个 PoC 工具；目录批量传输、文本预览、改名、移动和删除尚未提供。
- 文件传输不支持断点续传；失败重试会从头开始。
- 下载暂存目录不会自动清理，需要使用者自行管理磁盘空间。
- 同时向同一远程路径写入文件可能产生竞争，请避免多个客户端并发修改同一个目标文件。

## 许可

本项目基于 MIT License 开源。版权所有 (c) 2026 Ftrans，完整许可条款见 [LICENSE](LICENSE)。
