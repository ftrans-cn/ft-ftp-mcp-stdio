# 下一轮研发执行清单

> 性质：非规范性实施清单
> 状态：Completed
> 创建日期：2026-09-20
> 最近修订日期：2026-09-23
> 关联 Spec：`docs/spec/changes/next-development.md`
> Spec 状态：`Implemented`（2026-09-23）
> 关联 ADR：`0001`、`0002`、`0003`、`0006`、`0007`、`0008`；`0004` 已由 `0006` 取代，`0005` 已由 `0007` 取代
> 设计评审：`docs/development/reviews/next-development-design-review.md`
> 文档基线 SHA：`e3a8515333de6cebc555a24ac27aa5ff81e1e513`
> Start SHA：`1e816078458b41ea2a7518a8561aa6558ee2daf4`
> 首个 Candidate SHA（审查未通过）：`bdcf5ecd8076cecacc8551140104acb827dc200f`
> 整改 Candidate SHA：`459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712`
> P2 修复 Candidate SHA：`0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`
> Release Candidate SHA：`a6431909bdc82e9aec1070fc6635ddaa27dd186a`
> 发布状态：`0.3.0` 已于 2026-09-23 批准正式发布并完成本地 Git 归档；尚未推送或正式分发

首轮独立代码审查结论记录于 `docs/development/reviews/next-development-code-review.md`：5 项 P1、2 项 P2，必须修复并创建新 Candidate；原 Candidate 保持不变。

第二次独立代码复审结论为通过：P0/P1/P3 均为 0，上一轮 7 项问题全部关闭；新增 1 项非阻断 P2。项目负责人选择在当前阶段修复该 P2，因此整改 Candidate 保持不变，另行固定 P2 修复 Candidate 并等待独立增量复审。

第三次独立增量代码复审确认原 P2-1 已完整关闭，P0/P1/P2/P3 均为 0，不需要新 Candidate；最终 Candidate `0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1` 允许进入最终验收和发布准备。

本文件只跟踪实施顺序、验证状态、证据和提交边界。公共契约、安全边界、错误语义及验收标准以关联 Spec 和有效 ADR 为准。实施中如需改变这些内容，必须先停止相关实现，修订 Spec/ADR 并完成必要复审。

## 1. 使用约定

- 状态使用 `[ ]` 未开始、`[-]` 进行中、`[x]` 已完成、`[!]` 阻塞。
- 验收证据状态使用 `未运行`、`通过`、`失败`、`跳过` 或 `不适用`，并附命令、测试名、宿主记录或原因。
- 每个计划提交必须保持代码、测试和直接相关文档一致，不制造不可运行的中间状态。
- 每个实现提交至少运行一次非 live 全量 `uv run pytest`；专项测试不能替代提交前全量回归。
- 未经用户授权不执行 live 测试、远端清理、发布、部署、推送、合并、变基或标签操作。
- 本清单可以摘录验收检查点，但不得成为与 Spec 并列的契约来源。

## 2. 当前文档门禁

- [x] 已形成第一轮独立设计评审记录，结论为“不通过，阻塞实现”。
- [x] 项目负责人已逐项确认评审意见的采纳、部分采纳和替代处理方案。
- [x] Spec 已恢复为 `Draft`，并完成对应整改。
- [x] ADR 0006 已取代 ADR 0004 并纠正协议及本地链接范围；ADR 0007 已按项目负责人确认的首次检查快照语义取代 ADR 0005。
- [x] 本清单已按整改后的 Spec 重建，删除旧批次限制、旧 annotations 和旧错误映射。
- [x] 第一轮增量复审已记录：6 项 P1 关闭，上传临时对象与 `overwrite=false` 的并发语义仍不通过。
- [x] 项目负责人已明确不采纳原子独占/no-replace 门禁，接受首次检查后的目标与临时名称竞态，并要求以 ADR 0007 固化。
- [x] 将修订后的 Spec、有效 ADR、评审记录、缺陷台账和本清单提交为新的固定文档基线。
- [x] 在本清单记录新的文档基线 SHA 和 Start SHA。
- [x] 由独立上下文对新的固定文档基线进行增量复审。
- [x] 第二次独立增量复审确认 P0/P1 已关闭，且项目负责人对剩余风险的接受已形成自洽契约。
- [x] 项目负责人确认复审结论后，将 Spec 状态改为 `Accepted`。

完成条件：固定文档基线已复审，Spec 为 `Accepted`。在此之前不得进入代码实现。

### Candidate 前宿主边界修订门禁（2026-09-23）

- [x] 项目负责人确认接受当前宿主结果：服务端 annotations 已在 Codex 完成端到端验证；WorkBuddy 模型侧不可见，但能正常调用并正确处理结构化错误与 `indeterminate`。
- [x] 新增 ADR 0008，明确服务端 annotations 保证与第三方宿主内部处理的责任边界。
- [x] 将 Spec 暂退为 `Draft`，同步修订 §5、§17、§18、§19、PRD 和 A37。
- [x] 固定本次待审文档基线；SHA 见本节下方记录。
- [x] 由独立上下文对本次文档增量进行设计复审；第三次独立增量设计复审 P0/P1/P2/P3 均为 0，结论通过。
- [x] 项目负责人确认复审结论，ADR 0008 和 Spec 已更新为 `Accepted`。

待审文档基线 SHA：`81040b40583603f543223f683f74650b3a479c50`。独立复审范围为 `git diff a5ab9d3616d2015f8897fce66b95b03b085fe0de 81040b40583603f543223f683f74650b3a479c50`，并应核对其后的 SHA 回填提交只修改本记录；未提交整改实现仅作为既有证据，不属于本次设计基线。

## 3. 实现启动门禁

- [x] 记录实现分支、工作区、暂存区和 Start SHA；暂存区必须为空。
- [x] 在独立分支实施；本轮为单人、无并发任务，不创建 worktree。固定 Start/Candidate SHA 和按路径暂存保证候审范围可复现。
- [x] 确认启动时工作区和暂存区为空，不存在会混入本轮提交的无关用户改动。
- [x] 将 BUG-001、BUG-002、BUG-004、BUG-006、BUG-008、BUG-009 更新为 `In Progress`；BUG-003、BUG-010 保持 `Won't Fix`。
- [x] 记录基线测试：`uv run pytest`、`uv run ruff check .`、`uv run mypy src tests`。
- [x] 确认锁定的 FastMCP/MCP SDK 版本，并保存以下能力基线：根级 `type:object + oneOf`、`isError=true` 的 `structuredContent`、annotations/title、枚举调用前拒绝、框架参数错误。
- [x] 确认 Codex、WorkBuddy 的可用版本和真实宿主测试方式；任一正式宿主不可验证时阻塞交付。
- [x] 确认 FTP/SFTP live 测试授权、远端测试根和清理范围；无授权时记录跳过原因。
- [x] 对当前服务器 alias 执行连接预检；失败项须在对应协议的完整 live 测试前修复或替换。
- [x] 备份本机配置与 known-hosts，记录原权限及 staging 初始状态。
- [x] 记录代码回退方式：代码、Schema、测试和文档整体回到 Start SHA。
- [x] 记录外部状态边界：Git 回退不撤销配置替换、known-hosts、staging、远端写入或 `outcome_unknown`；只清理归属可证明的测试对象。

启动证据（2026-09-22）：

- 实现分支：`feature/next-development`；仓库工作目录：`D:\Documents\AIProject\Codex\FTP MCP\ft-ftp-mcp-stdio`；Start SHA：`1e816078458b41ea2a7518a8561aa6558ee2daf4`。切分支前工作区和暂存区为空。
- 基线测试：`uv run pytest -q` 为 `112 passed, 10 skipped`，跳过项为未授权 live 测试；`uv run ruff check .` 为 `All checks passed`；`uv run mypy src tests` 为 `Success: no issues found in 31 source files`。
- 本机备份目录：`C:\Users\zhuxu\.ft-ftp-mcp\development-backups\20260922-start-1e81607`。`config.json` SHA-256 为 `62E014EA6BA1F1CB38491275BFCEA3A27B6C707BA2F224456C9F4CCB8F945E42`；`known_hosts` SHA-256 为 `77C67A9476E756F3CDD872FA74E301CC6D41538504CF4B2884C16C74C8FC4F2A`；备份与原文件哈希一致。
- 两个原文件及备份的所有者均为 `SurfaceLaptop5\zhuxu`；有效权限均为当前用户、SYSTEM、Administrators 完全控制，`CodexSandboxUsers` 读取与执行。
- staging 启动时已有 8 个顶层目录，均视为本轮之前的对象，不得自动清理：`119e7b44bb7a4f14a9e46a30863b6949`、`391aa83dc27543dc9e8aa12554a169b1`、`49bffd26e45c4f3692d7b32acdb4a07d`、`617425814fcd427592e2ff569e0fa04f`、`6455807cb3984e9c8fbd08bf0c9d213f`、`9e3417ca7ce945b7a81ddca1373b4fdf`、`c13caf58c38641dc8601d888f15c568e`、`d6a8363bd2d84ad082fcb95e263bd35f`。
- SDK 锁定版本：FastMCP `4.0.2`、MCP SDK `2.1.1`、mcp-types `2.1.1`。执行 `uv run python scripts/probe_mcp_contract.py`，根级 `type:object + oneOf`、运行时错误保留 `isError=true + structuredContent`、工具 title/annotations、非法枚举进入工具函数前拒绝、框架参数错误 `structuredContent=null` 五项均通过。探针同时验证非法请求未执行工具函数。
- 正式宿主基线：Codex 桌面包 `26.915.4065.0`（CLI `0.155.0-alpha.9.2`）；WorkBuddy `5.5.6`。两者均已注册并启用 `ft-ftp-mcp-stdio` STDIO 配置，WorkBuddy 已存在对应信任记录。Codex 使用共享 MCP 配置和 `codex mcp`/真实会话验证；WorkBuddy 使用连接器管理、完全重启后的真实会话验证。
- 两宿主配置共同指向的已安装虚拟环境曾引用已删除的系统 Python。2026-09-22 已把旧环境保留为 `C:\Users\zhuxu\AppData\Local\ft-ftp-mcp\venv.broken-20260922-before-repair`，使用 uv 管理的 Python `3.12.13` 在原路径重建环境，并从仓库 `wheels` 离线安装 `ft-ftp-mcp-stdio 0.2.2`、FastMCP `4.0.2`、MCP SDK/mcp-types `2.1.1`。真实 STDIO 初始化和 `tools/list` 成功，发现当前 13 个工具。Codex/WorkBuddy 下次重连或重启将继续使用不变的注册路径；当时的 A37 要求已由 2026-09-23 重新接受的 ADR 0008 和 Spec 责任边界取代。
- 环境修复及宿主恢复期间检测到 `config.json` 和 `known_hosts` 被其他会话或进程持续更新；虚拟环境重建和离线安装均未写这两个文件。本次修复不覆盖动态外部状态，启动前原文件仍保存在上述 development-backups 目录。项目负责人确认配置和 known-hosts 均为低成本测试状态，后续 live 验证不要求重复备份。
- 项目负责人已授权 FTP/SFTP live 测试，并确认当前 FTP 服务器目录均为测试数据。测试可按需创建和清理独立 `/mcp_*` 目录；仍使用独立目录隔离不同测试运行并便于定位失败。本轮实际目录和上传临时命名空间在完整 live 测试开始时记录。
- 连接预检使用当前配置逐一调用 `test_connection`，未创建、修改或删除远端对象。初检中 `sftp-key-nopass-v2`、`sftp-key-pass-v2` 通过，`ftp1` 和 `sftp1` 因仍使用默认端口而失败；将端口分别修正为 `2121`、`2022`，并移除旧端点对应的 `sftp1` known-hosts 记录后，`ftp1`、`sftp1` 最终复检均通过，`sftp1` 已按 TOFU 重新记录当前端点指纹。FTPS 虽由测试服务器提供，但不纳入本轮产品和 live 验收范围；别名和 v2 配置在阶段二及阶段九同步到新版 live 用例。

## 4. 计划提交映射

| 顺序 | 计划提交 | 主要内容 | 前置阶段 |
| --- | --- | --- | --- |
| 0 | `Baseline revised development contract` | Draft Spec、ADR、评审整改、缺陷台账和本清单 | 当前文档门禁 |
| 1 | `Define closed MCP result contracts` | 统一成功/错误模型、13 个错误类型、Schema 构造与净化 | 实现启动门禁 |
| 2 | `Enforce config v2 and host trust` | 配置 v2、默认只读、三态加载、list_servers、TOFU 前置验证与并发持久化 | 1 |
| 3 | `Enforce virtual path boundaries` | 虚拟路径、远端目录项防逃逸、SFTP/FTP 链接策略 | 1、2 |
| 4 | `Align read and download behavior` | 只读输出、预览、UTC、下载完整性与清理 | 1、3 |
| 5 | `Commit uploads through safe temporary objects` | 本地链接检查、逐文件上传上限、同目录临时对象和安全提交 | 1、2、3 |
| 6 | `Harden write recovery semantics` | 写操作快照、证据、delete 判据、禁止盲目重放 | 1、3、5 |
| 7 | `Structure batch outcomes` | 无批次上限、逐项状态、相对路径、indeterminate | 4、5、6 |
| 8 | `Publish precise MCP contracts` | 14 工具描述、instructions、annotations、输入/输出 Schema、线级测试 | 2 至 7 |
| 9 | `Synchronize user and architecture documentation` | 正式 Schema、配置规范、用户文档、架构、live 脚本 | 2 至 8 |

实施中可以调整提交边界，但必须记录原因；不得把互相依赖、单独无法验证的改动强行拆开。

## 5. 阶段一：封闭结果与错误契约

涉及：`models.py`、`errors.py`、`server.py`、Schema 构造和对应测试。

- [x] 集中定义第 11.7 节全部成功结构及共享封闭类型。
- [x] 固化 13 个 `error_type`：`invalid_config`、`credential_missing`、`invalid_argument`、`not_found`、`invalid_path`、`symlink_unsupported`、`policy_rejected`、`size_limit_exceeded`、`permission_denied`、`connection_unavailable`、`integrity_check_failed`、`server_error`、`outcome_unknown`。
- [x] 实现封闭 discriminated union：普通错误禁止 `details`，上传超限和结果不确定分别强制对应 details。
- [x] 实现 `upload_limit_details`、`outcome_unknown_details`、`evidence_item`、批量错误及跳过枚举；每层 `additionalProperties:false`。
- [x] 所有对外失败固定 `retryable:false`；内部是否重试由执行阶段和证据决定。
- [x] 区分 FastMCP 调用前参数错误与运行时业务错误。
- [x] 建立敏感信息净化与精确 denylist 测试辅助，不扫描用户内容、预览内容、合法文件名、虚拟路径、alias 或 description。
- [x] SFTP 可确定不存在时映射为 `not_found`，且不触发连接类自动重试。
- [x] 为所有错误变体增加正反例测试，主动校验 `isError=true` 的结构化对象。

验证：`tests/test_errors.py`、`tests/test_schema.py`、相关 service/driver 测试；提交前执行全量 pytest、ruff、mypy。

## 6. 阶段二：配置 v2、服务器发现与 SFTP 信任

涉及：`models.py`、`config.py`、`config_store.py`、`setup_wizard.py`、`doctor.py`、`service.py`、`server.py`、配置 Schema 和测试。

- [x] 配置只接受 `version:2`；root 必填；`readOnly` 默认 true；description 为可选非空字符串且最长 200 字符。
- [x] 删除 `max_batch_files`、`max_batch_total_bytes`，`max_file_size_bytes` 接受非负整数且 `0` 表示不限制。
- [x] setup 只在无现有配置时创建 v2；其他版本不迁移、不覆盖，并提示备份和显式替换。
- [x] setup 对 root、协议专属字段及可确定字段组尽早校验，覆盖返回、取消和失败不落盘。
- [x] doctor 对 description 疑似敏感内容告警但不阻断；同步安全默认值和 root 风险提示。
- [x] 实现配置三态加载：默认路径缺失、合法配置、存在但不可读/非法；显式环境路径缺失必须是 `invalid_config`。
- [x] 实现 `list_servers`，只返回 alias、description、protocol、read_only、is_default，不读取凭据、不连接、不触发 TOFU。
- [x] 未知 alias 不枚举服务器；`test_connection` 删除连接、账号、root 和凭据来源。
- [x] 在用户认证前完成配置指纹或 known-hosts 比较；失败时不得发送密码或私钥签名。
- [x] known-hosts 以 alias 为键保存算法和指纹；配置指纹验证成功与首次 TOFU 均同步记录，但不写回配置文件。
- [x] 使用跨进程互斥、同目录临时文件和原子替换；损坏、重复冲突、锁失败、权限失败及持久化失败一律 fail-closed。
- [x] 只读拒绝发生在凭据读取和连接建立前。
- [x] 更新所有 v1 fixture、CLI、doctor 和服务测试，防止局部测试掩盖跨模块失败。

验证：配置/setup/doctor/CLI/server discovery/known-hosts 并发与故障专项测试；提交前执行全量 pytest、ruff、mypy。

## 7. 阶段三：虚拟路径、目录项与链接边界

涉及：`paths.py`、`service.py`、FTP/SFTP driver 和对应测试。

- [x] 实现虚拟 `/` 到配置 root 的正向映射与真实路径到虚拟路径的反向映射。
- [x] 拒绝空路径、非绝对路径、反斜杠、NUL、完整 `..` 段，规范化 `.`，并复核 root 边界及相似前缀。
- [x] 禁止删除、重命名、移动虚拟根，或把其他对象移动为虚拟根。
- [x] 把远端目录项名称作为不可信单组件输入，拒绝空、`.`、`..`、NUL、分隔符、绝对前缀、盘符、UNC 和目标平台保留/非法名称。
- [x] 每次构造下载目标后验证仍位于随机 staging 根；`download_dir` 非法项进入 `failed(invalid_path)`，单文件/list/search 使用工具级 `invalid_path`。
- [x] SFTP 从配置 root 开始逐段 `lstat`；root 链接为 `invalid_config`，路径链接为 `symlink_unsupported`，能力或结果不确定时 fail-closed。
- [x] `list_dir` 仅显示链接自身的安全属性；search 不进入/返回链接；批量工具逐项跳过链接，批量根为链接时工具级拒绝。
- [x] FTP 只在明确识别链接时拒绝/跳过，不宣称提供可靠链接隔离；Serv-U Virtual Path 按服务器普通目录处理。
- [x] 确认代码、Schema 和测试中没有把 FTPS 加入本轮范围。
- [x] 覆盖真实 root 泄露、恶意底层异常、目录项逃逸、断裂链接、链接循环、检查失败及 SFTP TOCTOU 可观察分支。

验证：路径、service、driver、安全输出专项测试；提交前执行全量 pytest、ruff、mypy。

## 8. 阶段四：读取、文本预览、时间与下载完整性

涉及：`service.py`、FTP/SFTP driver、staging 管理和对应测试。

- [x] 收敛 `list_dir`、`search_files`、`get_file_info`、`download_file` 的输出字段。
- [x] `max_bytes` 在运行时校验 1..1048576，越界返回 `policy_rejected`，不静默钳制。
- [x] 实现 UTF-8、UTF-8 BOM、GBK，按完整字符边界截断并准确返回行数、截断和 partial_line。
- [x] FTP 合法 MLSD/MDTM 按协议 UTC 输出，LIST 返回 null；SFTP 时间戳按 UTC；非法、越界或矛盾值返回 null。
- [x] 下载失败、取消或连接异常清理部分文件；清理失败返回 `server_error` 并说明可能残留。
- [x] 已知远端大小与落盘大小不一致，或能证明传输中来源变化时，返回/记录 `integrity_check_failed` 并清理无效文件。
- [x] 未知大小且正常 EOF 允许成功并返回实际大小；异常中断返回 `connection_unavailable`；下载不使用 `outcome_unknown`。
- [x] `download_dir` 单项失败进入 failed 并继续；整批无法开始时返回工具级错误。
- [x] 测试已知大小匹配/不匹配、未知大小正常 EOF/异常、来源变化、取消、driver 异常和清理失败。

验证：预览、mtime、download、staging 专项测试；提交前执行全量 pytest、ruff、mypy。

## 9. 阶段五：本地上传边界、逐文件限制与安全提交

涉及：`service.py`、driver 上传接口、本地文件辅助模块和对应测试。

- [x] `upload_file` 在凭据和连接前检查本地文件及稳定可得大小；正数上限边界允许，预检超限返回 `size_limit_exceeded + limit_details`。
- [x] `upload_file` 和 `upload_dir` 都在实际读取中累计字节，防止预检后增长；`0` 不限制。
- [x] `upload_dir` 不预扫描整个目录，逐项处理；单项超限安全清理后进入 `skipped(size_limit_exceeded)` 并继续。
- [x] 检查本地上传根、每级目录和最终文件的 symlink、junction、reparse point；枚举时、打开前和读取前通过句柄复核身份。
- [x] 链接、对象替换或无法可靠检查时，在读取任何字节前 fail-closed；单文件工具级拒绝，批量单项跳过或失败。
- [x] 远端临时对象使用最终目标同目录的 `.<目标文件名>.ft-upload-<16hex>.tmp`，以密码学安全 64 位随机源生成；初始名称冲突最多重试 3 次，3 次后 `server_error`，不向 Agent 返回名称。
- [x] 完整写入、未超限、远端句柄关闭及必要校验通过后才提交；不得先删除最终目标。
- [x] `overwrite=false` 每个文件只在上传前检查一次目标：当时存在即 `policy_rejected`，当时不存在即授权随后普通 rename；提交前不二次检查，也不要求原子 no-replace。
- [x] 明确实现已接受竞态：目标或临时名称在检查后被并发创建/替换时如实处理服务器结果；明确目标冲突为 `policy_rejected`，其他明确 rename 失败为 `server_error`，不得删除或强制替换服务器拒绝的目标。
- [x] `overwrite=true` 只在 driver 确认服务器支持安全原子替换时允许；能力未知或不支持时 `policy_rejected`。
- [x] 提交响应丢失禁止重放并返回/记录 `outcome_unknown`；临时清理失败按最终状态确定性返回 `server_error` 或 `outcome_unknown`。
- [x] 测试超限、增长、临时名称格式与 3 次冲突、检查后临时占用、首次目标检查与检查后并发目标、写入/关闭/rename/清理失败、原子替换有无能力及 FTP/SFTP 差异。

验证：上传限制、本地链接、安全提交和 driver 能力专项测试；提交前执行全量 pytest、ruff、mypy。

## 10. 阶段六：写操作恢复与结果核验

涉及：`service.py`、driver 接口、证据模型和可注入故障测试。

- [x] 区分只读与写操作执行路径；禁止写操作沿用整段盲目重试。
- [x] 为 make_dir、upload、rename、move、delete 获取规范要求的操作前快照和可用身份/内容证据。
- [x] 仅在能证明请求未开始时允许一次重试；可能已执行且证据不足时返回 `outcome_unknown`。
- [x] FTP `unique` 只作为 rename/move 身份证据；不得用其证明 delete 的因果成功。
- [x] delete 请求发出后连接中断或响应丢失一律 `outcome_unknown`，不得重放。
- [x] upload 只有远端可靠内容哈希匹配时才能从响应丢失恢复为成功；名称、存在性、mtime、大小或临时路径均不足够。
- [x] make_dir、rename、move 按 Spec 的成功证据和并发替换规则判断。
- [x] fake driver 覆盖请求前断线、服务端可能完成但响应丢失、核验失败、并发重建/替换，以及 SFTP、无 FTP unique、有 FTP unique。

验证：错误、service、fake driver 恢复矩阵；提交前执行全量 pytest、ruff、mypy。

## 11. 阶段七：批量结构化结果

涉及：批量 service 流程、模型、工具描述和对应测试。

- [x] 删除 `max_files` 参数和全部客户端文件数量/批次总字节限制；下载不应用单文件大小限制。
- [x] `file_count`、`total_size` 只统计成功项，不作为限制判据。
- [x] download_dir 仅使用 complete/partial/failed；不含 indeterminate，不使用 outcome_unknown。
- [x] upload_dir 使用 complete/partial/failed/indeterminate，并始终返回必填 indeterminate 数组。
- [x] 下载明细 path 为虚拟远程路径；上传明细和 evidence path 为相对于 local_path 的规范化相对路径。
- [x] 固化 batch skipped/failed/indeterminate 和 evidence 的封闭枚举；上传超限只进入 skipped。
- [x] `ok:true` 只表示批量工作流完成；工具描述要求检查 status、failed、indeterminate。
- [x] `status=indeterminate` 时不建议或自动整体重跑，只允许用户核验后重试明确单项。
- [x] 覆盖合法空目录、全部跳过、部分失败、全部失败、部分成功和单项不确定。

验证：批量模型、状态映射、路径语义和失败矩阵；提交前执行全量 pytest、ruff、mypy。

## 12. 阶段八：MCP Schema、元数据与宿主能力

涉及：`server.py`、Schema 导出、MCP 线级测试和真实宿主验证。

- [x] 更新服务 instructions，所有远端路径使用虚拟路径，不再要求真实服务器绝对路径。
- [x] 为全部 14 个工具更新中文 title、description、字段 description 和 annotations。
- [x] 只有 `list_servers.readOnlyHint=true`；其他工具因可能写入 TOFU 均为 false；写工具的 destructive/idempotent 提示与 Spec 一致。
- [x] `pattern` 运行时非法返回 `invalid_argument`；confirm/max_bytes 等保持规定的框架/运行时分层。
- [x] 所有输出 Schema 根节点为 object，内部 oneOf 成功/错误；完整展开 required、枚举、可空性和 additionalProperties:false。
- [x] 验证成功结果由 MCP Client 校验；项目测试主动校验全部错误对象；框架错误保持 `structuredContent=null`。
- [x] 比较运行时 `tools/list` 的完整工具名集合、服务版本、title、description、annotations 和 Schema 快照。
- [x] 保存 FastMCP 能力探测证据；任一关键行为不支持时停止并退回 Spec，不做静默兼容。
- [x] 验证服务端 annotations、Codex 模型侧端到端可见性，以及 Codex/WorkBuddy 的工具发现、参数拒绝、`isError=true` 错误可见性和 upload_dir indeterminate 告警/不整体重跑；WorkBuddy 模型侧 annotations 不可见按 ADR 0008 记录为宿主能力限制。

验证：MCP 线级测试、Schema 导出无差异、两个正式宿主的阻塞性记录；提交前执行全量 pytest、ruff、mypy。

## 13. 阶段九：文档、live 环境与治理同步

实现过程中同步：

- [x] `docs/schema/config.schema.json`、`config.example.json` 与配置 v2 实现一致。
- [x] 从运行时重建 `docs/schema/mcp-tools.json`，不得手工伪造最终快照。
- [x] 新版配置规范、用户手册、PRD、产品能力清单与 CLI 手册反映新契约；保留旧版本历史。
- [x] 更新 `README.md`、`docs/architecture.md`、`docs/MVP架构图.svg`。
- [x] 仅在版本化文档文件名或治理入口变化时更新 `AGENTS.md`。
- [x] 不把历史 MCP Schema 草案、旧 PRD、旧能力清单或旧测试报告改写成当前事实；治理入口不再引用其为当前依据。
- [x] 检查 `scripts/make_fixtures.py`、`upload_fixtures.py`、`cleanup_live_dirs.py` 的虚拟路径、alias 和临时命名空间；修订或记录不适用理由。
- [x] 明确 ruff/mypy 是否覆盖 scripts，并保持命令口径一致。
- [x] 改造 `tests/test_live.py` 到 v2、虚拟路径和新输出契约；授权下准备 FTP/SFTP v2 live 配置和可清理远端根。
- [x] 首次运行完整 live 测试前，记录本轮实际远端测试目录、上传临时命名空间及其初始状态。
- [x] 每次 live 运行后只清理归属明确的测试目录和临时对象，并记录 `outcome_unknown` 人工核验。
- [x] 缺陷实现完成后更新为 `Fixed`，独立验证后更新为 `Verified`；发布后才更新为 `Released`。

阶段一至九实现证据（2026-09-22）：

- 非 live 候选回归：`uv run pytest -q -rs` 为 `119 passed, 11 skipped`；其中 10 项是未启用 `--live`，1 项因当前 Windows 环境不能创建测试 symlink 而跳过，其余链接/reparse point 契约由 fake/平台测试覆盖。
- 静态检查：`uv run ruff check .` 通过；统一类型检查命令 `uv run mypy src tests scripts` 检查 42 个源文件通过。
- FastMCP 契约探针五项全部通过；`docs/schema/mcp-tools.json` 从运行时重建前后 SHA-256 均为 `CA7BFABD7CA8C5808819BE7B0FB9C84D7EE0054C6F81C6FBD3B42EA585081248`。
- 隔离 live 配置位于 `.pytest-temp/next-development-live/config.json`，由当前 v1 测试配置生成，不覆盖主配置；仅 `ftp1`、`sftp1` 显式可写，专用 staging 尚未创建。`ftp1` 缺失的 v1 root 通过命令行显式指定为 `/`，保留 ADR 0002 已接受的服务端隔离风险。只读 SFTP 初始探测在同目录专用 `known_hosts` 中登记了 1 条 `sftp1` TOFU 记录，未修改主 known-hosts。
- 本轮远端测试根固定为 `ftp1:/mcp_ftp_next_development_20260922` 与 `sftp1:/mcp_sftp_next_development_20260922`。首次完整 live 前的只读探测确认两者均不存在：FTP 父目录精确名称匹配为 0，SFTP 返回 `not_found`。
- 上传临时命名空间固定为同目录 `.<目标文件名>.ft-upload-<16hex>.tmp`。隔离配置下执行精确命令 `uv run pytest -q --live`，FTP 与 SFTP 最终为 `129 passed, 1 skipped`；唯一跳过项是当前 Windows 环境不能创建本地测试 symlink。过程中未出现 `outcome_unknown`。
- 首次失败运行暴露 FTP 预览 ASCII 模式换行转换和 MLSD 时间未规范化导致的完整性误报；修复并增加回归测试后完整 live 通过。每次运行后仅清理上述两个固定远端根及专用 staging；最终只读复核为 FTP 父目录精确匹配 0、SFTP 根 `not_found`、专用 staging 不存在。
- 正式 Codex 宿主通过真实 stdio MCP 完成 14 工具发现、`list_servers`、框架参数拒绝和 `max_bytes=0` 结构化 `policy_rejected`；正式 WorkBuddy 宿主完成 14 工具发现、`list_servers`、同一运行时错误可见性，并在调用前按 JSON Schema 拒绝字符串 `max_bytes`。两宿主共同使用的已安装环境已从当前工作区重装，五项框架能力探针全部通过；`upload_dir` 的工具描述明确要求检查 `indeterminate` 且不得整体重试，契约测试验证该结果结构。

首轮独立审查后整改证据（2026-09-22）：

- 审查报告已由 `a5ab9d3616d2015f8897fce66b95b03b085fe0de` 固定；原审查结论保持不变，整改映射追加在该报告末尾。
- 非 live 回归 `uv run pytest -q -rs` 为 `149 passed, 11 skipped`；10 项因未启用 `--live`，唯一平台跳过严格限定为 Windows 创建文件 symlink 返回 `WinError 1314`。真实 Windows junction 覆盖根、父目录和断裂 junction；reparse point 属性与打开后句柄身份不一致均验证在读取首字节前拒绝。
- `uv run ruff check .` 通过；`uv run mypy src tests scripts` 检查 44 个源文件通过；FastMCP 五项探针通过。运行时重新导出 `docs/schema/mcp-tools.json` 后 SHA-256 仍为 `CA7BFABD7CA8C5808819BE7B0FB9C84D7EE0054C6F81C6FBD3B42EA585081248`，无差异。
- 最终完整 live 重跑 `uv run pytest -q --live -rs` 为 `159 passed, 1 skipped`，未出现 `outcome_unknown`；此前一次完整运行发生 FTP 上传完成后立即枚举少一项，单项重跑通过，最终完整重跑也通过。清理后只读复核为 FTP 父目录精确匹配 0、SFTP 根 `not_found`，专用 staging 清理 4 个本轮下载目录后剩余 0。
- 共享宿主虚拟环境已从最新整改工作区重新安装。Codex 正式宿主实调 `list_servers` 和 `max_bytes=0`，分别得到结构化成功与 `isError=true` 的 `policy_rejected`；专项 fixture 实调确认 `upload_dir status=indeterminate`、`outcome_unknown`、写工具 annotations 和不整体重跑。WorkBuddy 专项 fixture 仅调用一次，正确识别 `status=indeterminate`、`outcome_unknown` 并明确不整体重试；后续只读工具元数据检查显示其模型侧看不到四种 annotations。当前只能确认模型侧不可见和工具可正常调用，尚未通过原始 `tools/list` 入站报文确定 WorkBuddy 内部的具体丢失层级。项目负责人于 2026-09-23 选择按 ADR 0008 将保证限定在服务端接口，同时保留两个宿主对错误和不确定结果的端到端门禁；临时 fixture 注册已从两个宿主配置移除。

第二次独立代码复审后 P2 修复证据（2026-09-23）：

- 第二次独立代码复审 P0/P1/P3 均为 0、P2 为 1，总体结论通过；上一轮 7 项问题全部关闭。报告由 `92983a1` 固定，并将根目录兼容性问题登记为 `BUG-011`。
- `BUG-011` 修复提交为 `0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`：本地路径检查在遍历子路径段前先检查文件系统根路径，避免根目录输入引用未初始化变量；回归测试覆盖当前平台根目录、非目录根对象和根路径缺失时不连接远端。
- 非 live 回归 `uv run pytest -q -rs` 为 `152 passed, 11 skipped`；10 项因未启用 `--live`，1 项因 Windows 创建文件 symlink 返回 `WinError 1314`。Ruff、mypy（44 个源文件）和 FastMCP 五项探针通过；Schema 重导出前后 SHA-256 均为 `CA7BFABD7CA8C5808819BE7B0FB9C84D7EE0054C6F81C6FBD3B42EA585081248`，无差异。
- 本次改动仅修复建立远端连接前的本地路径预检，未改变远端 driver、Schema 或 MCP 契约，因此没有重跑 FTP/SFTP live 写入矩阵；继续引用整改 Candidate 已完成的 `159 passed, 1 skipped` live 证据，等待独立增量代码复审确认该判断。

候选验证通过后更新：

- [x] `docs/spec/current.md` 写入已验证的当前行为，不在实现完成前提前改写。
- [ ] `RELEASE-NOTES.md` 在 Candidate SHA 和独立代码审查确定后新增发布记录，不改写历史条目。
- [ ] `docs/release.md` 仅在发布流程本身变化时更新；本轮默认不修改。

## 14. Spec §17 验收追踪

| ID | 验收主题 | 阶段 | 主要证据 | 状态 |
| --- | --- | ---: | --- | --- |
| A01 | 14 工具完整元数据与精确 Schema | 8 | `test_schema`；运行时 tools/list 与快照 | 通过 |
| A02 | setup 创建 v2 且不迁移覆盖旧配置 | 2 | `test_setup`、`test_config` | 通过 |
| A03 | 配置三态与显式路径缺失 | 2 | `test_config` discovery 三态 | 通过 |
| A04 | list_servers 无连接、凭据和敏感字段 | 2 | `test_service` 最小字段；两宿主实调 | 通过 |
| A05 | alias/description 选择且未知 alias 不枚举 | 2 | `test_service`、`test_config` | 通过 |
| A06 | test_connection 输出最小化 | 2、8 | service/Schema/live | 通过 |
| A07 | 虚拟远程路径和本机路径语义 | 3、7 | `test_paths`、service/live 批量 | 通过 |
| A08 | 服务生成信息的敏感 denylist | 1、3 | `test_service` 安全输出 | 通过 |
| A09 | denylist 不误杀用户内容 | 1 | description 与用户内容保留反例 | 通过 |
| A10 | root、点段、反斜杠、NUL 与真实路径误传 | 3 | `test_paths`；live 父段拒绝 | 通过 |
| A11 | 不可信目录项和本地落盘防逃逸 | 3、4 | 恶意目录项与 Windows 名称矩阵 | 通过 |
| A12 | 虚拟根操作保护 | 3 | `test_virtual_root_mutations_are_rejected` | 通过 |
| A13 | SFTP 逐段链接检查 fail-closed | 3 | contract/driver fake 矩阵 | 通过 |
| A14 | 链接展示、搜索与批量跳过 | 3、7 | service 批量状态测试 | 通过 |
| A15 | FTP 链接能力边界、虚拟目录、无 FTPS | 3 | driver、Schema、文档与 FTP live | 通过 |
| A16 | 本地 symlink/junction/reparse point | 5 | WinError 1314 精确跳过；真实 junction、reparse 属性、句柄身份竞态 | 通过 |
| A17 | 默认只读且连接前拒绝 | 2 | config 默认值与连接 spy | 通过 |
| A18 | 认证前主机密钥校验与安全持久化 | 2 | known-hosts/driver 故障矩阵；SFTP live | 通过 |
| A19 | TOFU 副作用对应 readOnlyHint=false | 2、8 | annotations 快照与能力探针 | 通过 |
| A20 | max_file_size_bytes 非负及 0 不限 | 2、5 | config/contract 上传测试 | 通过 |
| A21 | upload_file 上限和传输中增长 | 5 | service 预检、增长、清理矩阵 | 通过 |
| A22 | upload_dir 流式逐项超限 | 5、7 | contract 批量继续测试 | 通过 |
| A23 | 同目录 64 位随机临时对象、首次检查快照授权与安全提交 | 5 | service 临时对象/碰撞/提交测试；live | 通过 |
| A24 | 无数量/批次/下载大小限制 | 2、7 | v2 Schema 与批量行为回归 | 通过 |
| A25 | 文本预览范围、编码、字符和行语义 | 4 | preview 单测；FTP/SFTP UTF-8/GBK live | 通过 |
| A26 | FTP/SFTP mtime 规则 | 4 | driver 时间矩阵；live 完整性回归 | 通过 |
| A27 | download/upload 批量状态与路径 | 7 | service 状态矩阵；FTP/SFTP live | 通过 |
| A28 | 批量封闭枚举和逐项定位 | 1、7 | models/Schema/service 测试 | 通过 |
| A29 | 成功输出 Schema 强制校验 | 1、8 | MCP Client/Schema 测试 | 通过 |
| A30 | 运行时错误 isError/structuredContent | 1、8 | 线级探针；Codex/WorkBuddy 实调 | 通过 |
| A31 | 项目主动校验错误分支 | 1、8 | error/contract/Schema 测试 | 通过 |
| A32 | 框架参数错误 structuredContent=null | 1、8 | 线级探针；Codex/WorkBuddy 调用前拒绝 | 通过 |
| A33 | 运行时参数错误和上传超限详情 | 1、4、5、8 | contract/service；两宿主 `max_bytes=0` | 通过 |
| A34 | 错误 union 与 details 封闭性 | 1 | `test_errors`、`test_schema` 反例 | 通过 |
| A35 | outputSchema 根 object 反例 | 8 | 能力探针与 Schema 测试 | 通过 |
| A36 | SDK 版本变化重新探测 | 启动、8 | FastMCP 4.0.2、MCP/mcp-types 2.1.1 五项通过 | 通过 |
| A37 | 正式宿主 annotations 边界、错误与 indeterminate | 8 | Schema/MCP Client/探针；Codex annotations 端到端；两宿主错误与 indeterminate 实调 | 通过 |
| A38 | SFTP not_found 不连接重试 | 1 | contract matrix | 通过 |
| A39 | 写操作故障注入和三类身份能力 | 5、6 | 六类写操作请求前断线、响应丢失、核验失败及 FTP unique/SFTP/无身份矩阵 | 通过 |
| A40 | 写操作不盲重放且 outcome_unknown | 6 | 强哈希/身份成功证据、并发替换、清理不确定与禁止重放矩阵 | 通过 |
| A41 | 下载清理、大小和完整性 | 4 | service 下载矩阵；FTP/SFTP live | 通过 |
| A42 | 正式 MCP Schema 可重建无差异 | 8、9 | 导出前后 SHA-256 相同 | 通过 |
| A43 | 治理入口不引用历史草案为当前事实 | 9 | 文档检索与 current Spec 同步 | 通过 |
| A44 | pytest、ruff、mypy、Schema、授权 live | 9、候选 | 152/11、ruff、mypy 44、Schema 无差异、159/1 live | 通过 |

## 15. 候选验证与独立代码审查

- [x] 全量执行 `uv run pytest`。
- [x] 执行 `uv run ruff check .`。
- [x] 执行 `uv run mypy src tests scripts`。
- [x] 重建 MCP Schema 并确认无未预期差异。
- [x] 在授权范围内执行 `uv run pytest --live`，记录 FTP/SFTP 结果和清理证据；无授权则记录跳过及残余风险。
- [x] 按 ADR 0008 的已接受边界完成 Codex、WorkBuddy 真实宿主验证。
- [x] 逐项填写 A01-A44 的证据和状态；A37 已由第三次独立增量设计复审确认通过。
- [x] 更新 `docs/spec/current.md`、用户文档、架构文档和缺陷状态，使其与已验证实现一致；缺陷在独立代码审查前保持 `Fixed`。
- [x] 首个 Candidate 提交及 SHA 已记录，独立审查结论为不通过。
- [x] 创建整改 Candidate 提交并记录新 Candidate SHA；候审期间不改写该提交。
- [x] 独立审查 `git diff <StartSHA> <CandidateSHA>`，覆盖代码、测试、Schema 和文档；第二次独立代码复审已完成并通过。
- [x] 本次整改已独立审查 `git diff bdcf5ecd8076cecacc8551140104acb827dc200f 459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712`，并核对完整范围 `git diff 1e816078458b41ea2a7518a8561aa6558ee2daf4 459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712`。
- [x] 审查后代码修复已创建新 Candidate `0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`，未改写既有 Candidate。
- [x] 独立增量复审 `git diff 459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712 0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`，并核对完整范围 `git diff 1e816078458b41ea2a7518a8561aa6558ee2daf4 0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`；结论通过，P0/P1/P2/P3 均为 0。
- [x] 本次 P2 修复未改变核心设计或安全边界，无需退回 Spec/ADR 或重新执行设计审查。
- [x] 最后一次独立代码复审实际覆盖的 Candidate SHA 为 `0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`。

## 16. 回滚与外部状态恢复

- [ ] 代码回滚以 Start SHA 为整体边界，不部分保留不匹配的代码、Schema、测试或当前文档。
- [ ] 配置 v2 不承诺自动恢复为 v1；只使用启动门禁中人工确认的备份恢复路径。
- [ ] known-hosts 恢复时同时验证文件内容、权限和与代码版本匹配的格式。
- [ ] staging 和远端临时对象只按记录的命名空间与归属证据清理。
- [ ] `outcome_unknown` 逐项人工核验，不自动重放或删除归属不明对象。
- [ ] 已完成的远端用户数据变更明确不属于 Git 回滚范围。

## 17. 偏差记录

| 日期 | 原计划 | 实际调整 | 原因 | 是否修改 Spec/ADR | 状态 |
| --- | --- | --- | --- | --- | --- |
| 2026-09-21 | 旧清单基于批次数量/总量限制和旧错误契约 | 按整改后 Draft Spec 全量重建 | 产品决策和独立评审已改变安全及公共契约 | 是，已修订并等待复审 | 已记录 |
| 2026-09-21 | ADR 0005 的上传提交策略仍保留二次检查且未裁决原子能力 | 改为首次目标检查即授权、低成本随机临时名，并由 ADR 0007 取代 ADR 0005 | 项目负责人选择服务器兼容性优先并明确接受检查后的并发覆盖与临时名称竞态 | 是，已修订并等待再次复审 | 已记录 |
| 2026-09-23 | 两个正式宿主均须向模型透传 annotations | 服务端保证正确发送并至少由一个真实宿主端到端验证；其他宿主只保证接受并正常调用，错误与 indeterminate 仍逐宿主端到端验证 | 第三方宿主的模型注入策略不受 MCP Server 控制；Codex 已证明 annotations 有效，WorkBuddy 的关键运行时安全行为已通过 | 是，ADR 0008 与 Spec 已修订 | 独立增量设计复审通过 |

新增偏差必须先判断是否改变公共契约、安全边界或验收标准；若是，停止实现并先修订规范。

## 18. 完成条件

- [x] A01-A44 全部通过，或明确记录经项目负责人接受的跳过项及残余风险。
- [x] 最终 Candidate SHA 已通过独立代码审查，P0/P1 已关闭或被明确接受。
- [x] `docs/spec/current.md`、正式 Schema、实现和测试表达同一当前行为。
- [x] Spec 状态更新为 `Implemented`。
- [x] 缺陷台账更新至实际 `Fixed`/`Verified` 状态；发布后再进入 `Released`。
- [x] 最终报告包含 Start SHA、Candidate SHA、验证结果、跳过项、外部状态和残余风险。
- [x] 本清单状态更新为 `Completed`；发布完成后决定归档或删除，避免被误认为当前契约。

## 19. 最终验收摘要

- Start SHA：`1e816078458b41ea2a7518a8561aa6558ee2daf4`。
- 实现 Candidate SHA：`0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`；其后没有实现、测试、Schema 或构建输入变化。
- Release Candidate SHA：`a6431909bdc82e9aec1070fc6635ddaa27dd186a`；其后仅增加独立复审归档和最终发布证据。
- 最终独立发布复审：原 P1-1 和 P2-1 均已完整关闭，P0/P1/P2/P3 均为 0，总体结论通过，不需要新 Release Candidate。
- 非 live 验证：`154 passed, 11 skipped`；Ruff、mypy（46 个源文件）、FastMCP 五项探针和 Schema 无差异均通过。11 项跳过中，10 项是未启用 `--live`，1 项是 Windows 创建文件 symlink 返回 `WinError 1314`；junction、reparse 属性和句柄身份检查已有实际覆盖。
- Live 与宿主证据：最终完整 FTP/SFTP live 为 `159 passed, 1 skipped`，未出现 `outcome_unknown`；P2 修复完全位于 driver 创建前的本地预检，独立复审确认无需重跑 live。Codex 与 WorkBuddy 已按 ADR 0008 的责任边界完成真实宿主验证。
- 发布与外部状态：`0.3.0` 已于 2026-09-23 批准正式发布并以本地 annotated tag `v0.3.0` 归档；仓库没有远端，产物尚未推送或正式分发。授权 live 后固定 FTP/SFTP 测试根和专用 staging 已清理并只读复核；主配置与 known-hosts 属于用户接受的低成本测试状态，不属于 Git 回滚范围；本阶段未更新正式宿主安装环境。
- 残余风险：继续接受 Spec §19、ADR 0007 和 ADR 0008 已披露的限制，包括 WorkBuddy 模型侧 annotations 不可见、FTP symlink 能力边界、逐段检查后的 TOCTOU、首次检查后的并发覆盖/临时名竞态、本地上传无允许根白名单、无客户端批量总量限制及未知大小下载缺少一致快照证明。
