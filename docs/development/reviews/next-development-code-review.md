# next-development Candidate 独立代码审查

- 审查日期：2026-09-22
- 审查者：Codex 独立代码审查 Agent
- 审查性质：高影响变更的实现后独立代码审查
- 最终结论：**不通过，必须修复并创建新 Candidate。**

## 1. 实际覆盖范围

- Start SHA：`1e816078458b41ea2a7518a8561aa6558ee2daf4`
- Candidate SHA：`bdcf5ecd8076cecacc8551140104acb827dc200f`
- Candidate 记录提交：`475d32006c151f19fff880c6ece4f723796fea80`
- 正式 diff 命令：

  ```powershell
  git diff 1e816078458b41ea2a7518a8561aa6558ee2daf4 bdcf5ecd8076cecacc8551140104acb827dc200f
  ```

本轮审查了上述 diff 中的 49 个文件（10,759 行新增、2,132 行删除），包括实现、测试、正式 MCP Schema、配置 Schema、当前 Spec、执行记录、缺陷台账、用户文档和架构文档。`475d320` 只用于核验 Candidate 记录，不纳入产品实现审查范围。

## 2. 工作区和提交关系核验

- 当前分支为 `feature/next-development`。
- 审查开始时 HEAD 为 `475d32006c151f19fff880c6ece4f723796fea80`，工作区、暂存区均为空。
- Start、Candidate、记录提交均为有效 commit 对象。
- `git merge-base Start Candidate` 返回 Start SHA，且 `git merge-base --is-ancestor Start Candidate` 成功。
- `git merge-base --is-ancestor Candidate 475d320` 成功。
- Start 到 Candidate 共 10 个提交。
- `475d320` 仅修改 `docs/development/plans/next-development.md`，其中记录的 Candidate SHA 精确为 `bdcf5ecd8076cecacc8551140104acb827dc200f`；记录准确。
- Candidate 没有被改写或重新生成。

## 3. 契约来源

审查以以下资料为约束，不以 A01-A44 的勾选状态替代独立证据：

- Accepted Spec：`docs/spec/changes/next-development.md`
- 当前行为基线：`docs/spec/current.md`
- 有效 ADR：ADR 0001、0002、0003、0006、0007（ADR 0004、0005 已被取代）
- 正式 MCP Schema：`docs/schema/mcp-tools.json`
- 配置 Schema：`docs/schema/config.schema.json`
- 执行与验收记录、缺陷台账仅作为证据来源，不作为契约豁免。

## 4. 实际运行的检查

| 检查 | 结果 |
| --- | --- |
| `git status --short --branch` 及只读 SHA/祖先关系命令 | 通过；起始工作区干净，关系符合记录 |
| `git diff --check Start Candidate` | 通过 |
| `uv run pytest -q -rs` | 未进入测试逻辑；沙箱无权访问默认 pytest 临时根，产生 120 个 setup error。该结果属于运行环境错误，不计为 Candidate 测试失败 |
| `uv run pytest -q -rs -p no:cacheprovider --basetemp=.../.pytest-temp/independent-review-20260922` | `119 passed, 11 skipped`；10 项未传 `--live`，1 项为本机无法创建 symlink |
| `uv run pytest -q tests/test_schema.py -p no:cacheprovider --basetemp=.../.pytest-temp/review-schema-20260922` | `5 passed`；运行时 `tools/list` 与正式快照完整相等，配置样例通过配置 Schema |
| `uv run ruff check .` | 通过 |
| `uv run mypy src tests scripts` | 通过；42 个源文件 |
| `uv run python scripts/probe_mcp_contract.py` | 五项能力探针全部通过 |
| `Get-FileHash docs/schema/mcp-tools.json -Algorithm SHA256` | `CA7BFABD7CA8C5808819BE7B0FB9C84D7EE0054C6F81C6FBD3B42EA585081248`，与候选记录一致 |

本轮没有运行 FTP/SFTP live 测试，没有连接远端服务器，没有操作 Codex/WorkBuddy 正式宿主，也没有修改任何宿主配置或外部状态。

## 5. Findings

### P1-1：SFTP 创建目录绕过强制逐段 `lstat`，可沿符号链接父目录写入

- 分类：Candidate 新引入的问题；实现缺陷；阻断。
- 位置：`src/ft_ftp_mcp_stdio/service.py:246`、`:248`、`:375`、`:391`；相关跟随行为位于 `src/ft_ftp_mcp_stdio/drivers/sftp.py:169`、`:171`、`:181`、`:184`。
- 可触发场景：SFTP root 内已有目录段是符号链接时，调用 `make_dir`，或让 `upload_dir` 创建批量根/子目录。service 直接调用 `driver.exists`/`driver.make_dir`，未先调用 `_check_remote`；SFTP `exists` 使用会跟随链接的 `stat`，若链接目标目录存在便直接跳过该段，随后在链接目标下继续创建。
- 实际影响：写操作可越过配置 root 的词法授权边界，在符号链接指向的位置创建目录；也不会返回要求的 `invalid_config`/`symlink_unsupported`。这是路径逃逸和越权写风险。
- 违反契约：Accepted Spec §7.1 第 171-182 行、验收标准第 549-550 行；ADR 0006 的 SFTP 从 root 逐段 `lstat`、检测到链接即停止、检查不确定时 fail-closed 要求。
- 建议修复：所有带远端路径的创建流程在首次业务操作前执行统一逐段检查；对允许缺失的目标只允许最终缺失，既有父段必须完成 `lstat`。`upload_dir` 根路径链接应工具级拒绝，批量子项链接应逐项跳过；不要用会吞错且跟随链接的 `exists` 代替授权检查。
- 应补测试：真实 `SFTPDriver` fake channel 覆盖 root 段、中间段、最终段、断裂链接、`lstat` 不支持/权限/连接失败；分别断言 `make_dir` 与 `upload_dir` 不调用 `mkdir`，并覆盖批量根与子目录语义。

### P1-2：写操作恢复矩阵未实现，A39/A40 的通过结论没有对应实现

- 分类：Candidate 新引入的问题；实现缺陷及测试缺口；阻断。
- 位置：`src/ft_ftp_mcp_stdio/service.py:84`、`:246`、`:251`、`:278`、`:282`、`:301`、`:305`、`:484`；证据声称位于 `docs/development/plans/next-development.md:300`、`:301`。
- 可触发场景：`make_dir`、`upload_file`/`upload_dir`、`rename`、`move` 在请求前断线，或服务器完成操作但成功响应丢失。当前实现没有可区分“请求未开始”的阶段，没有重新连接后置核验，也没有对象身份、FTP `unique` 或远端内容哈希接口；所有连接异常均直接构造 `phase=response_wait`、`evidence=[]` 的 `outcome_unknown`。
- 实际影响：可以安全重试或可以根据强证据恢复为成功的调用被错误报告为不确定；更重要的是，执行记录声称已覆盖操作前快照、三类身份能力和核验失败，但代码与测试并不存在这些路径。Accepted Spec 的核心写恢复设计没有交付。
- 违反契约：Accepted Spec §15 第 475-501 行及验收标准第 575-576 行；执行清单阶段六关于操作前快照、强证据和“仅在证明未开始时一次重试”的承诺。
- 建议修复：为 driver/业务层引入明确的请求阶段和证据能力；按工具保存规定快照，连接异常后使用新连接执行只读后置核验，仅在证明请求未开始时重试一次；delete 发出后始终不重放；只有可靠哈希允许 upload 恢复成功；按协议能力记录封闭 evidence。
- 应补测试：Accepted Spec 明列的 fake-driver 矩阵，覆盖六类写工具、请求前断线、可能完成后丢响应、核验失败、并发重建/替换，以及 SFTP、无 FTP `unique`、有 FTP `unique` 三类能力。现有 `tests/test_contract_matrix.py:87` 只验证“连接错误不重放”，不足以证明恢复契约。

### P1-3：上传临时对象的存在/清理检查把连接和权限错误当作“不存在”

- 分类：Candidate 新引入的问题；实现缺陷；阻断。
- 位置：`src/ft_ftp_mcp_stdio/service.py:232`、`:233`、`:236`、`:452`、`:456`；`src/ft_ftp_mcp_stdio/drivers/ftp.py:187`-`:197`；`src/ft_ftp_mcp_stdio/drivers/sftp.py:169`-`:174`。
- 可触发场景：检查随机临时名或清理失败上传时，FTP/SFTP 的 size/stat/CWD 因连接中断、权限不足或协议错误失败。两个 `exists` 都把这些错误统一返回 `False`。临时名分配会把未知状态当成无冲突；失败清理会因 `exists=False` 跳过 delete，然后返回原始 `size_limit_exceeded` 或其他错误。
- 实际影响：可能覆盖检查状态不明的临时对象，或遗留包含本地数据的远端临时文件，却向调用方报告 `remote_committed=false` 的安全跳过/普通失败。清理状态和最终状态不确定性被隐瞒。
- 违反契约：Accepted Spec §12 第 382-385 行、§13 第 401-407 行；ADR 0007 的精确临时对象清理与响应不确定语义。
- 建议修复：将存在性查询改为三态或抛出语义化错误，只把明确 not-found 当作不存在；清理应直接对本次确切临时路径执行可判定删除/核验，连接或权限错误按最终目标可判定性映射为 `server_error` 或 `outcome_unknown`/批量 `indeterminate`。
- 应补测试：FTP/SFTP 分别覆盖临时名检查连接失败/权限失败、上传中断后存在性检查失败、delete 失败、delete 响应丢失，并断言不会报告安全 skipped、不会继续写未知临时对象。

### P1-4：A16 的 Windows symlink/junction/reparse point 证据不足

- 分类：测试与证据缺口；阻断。仅凭本次跳过不能断定实现必然错误，但不能据此接受安全边界。
- 位置：`tests/test_service.py:325`-`:335`，尤其 `:331`；实现入口为 `src/ft_ftp_mcp_stdio/service.py:526`-`:579`；错误通过声明位于 `docs/development/plans/next-development.md:243`、`:277`。
- 可触发场景：测试创建 symlink 时捕获所有 `OSError` 后跳过。除 `WinError 1314` 外，路径错误、文件系统错误、API 使用回归等同样会被隐藏。仓库没有创建 Windows junction 或其他 reparse point 的实际平台测试，也没有 fake 测试验证打开前替换、句柄身份不一致且零字节读取。
- 实际影响：Candidate 在唯一直接本机链接测试未运行的情况下把 A16 标为通过；junction/reparse point、断裂链接和 TOCTOU fail-closed 未获得 Accepted Spec 要求的证据。
- 违反契约：Accepted Spec §7.2 第 190-194 行及验收标准第 552 行；执行清单 A16 的“平台检查与 fake 竞态”证据声明。
- 建议修复：跳过条件仅限明确的平台能力错误（在当前环境至少精确判断 `winerror == 1314`），其他 `OSError` 让测试失败；增加无需 symlink privilege 的 Windows junction/reparse point 测试，并通过受控替换/fake file API 证明检查后替换在读取首字节前拒绝。
- 应补测试：根 symlink、父目录 symlink、最终文件 symlink、断裂链接、junction、其他 reparse point、枚举后替换、打开前替换、句柄身份不一致、检查 API 失败，且用读取 spy 断言读取字节数为 0。
- A16 判断：现有证据不足，不能标记通过；这是阻断性的测试/证据缺口，不是可接受的非阻断残余风险。补充测试会改变 Candidate 的测试内容，因此必须创建新 Candidate。

### P1-5：Codex/WorkBuddy 正式宿主证据未满足逐宿主阻塞验收

- 分类：测试与证据缺口；阻断。
- 位置：`docs/development/plans/next-development.md:220`、`:250`、`:298`、`:314`。
- 可触发场景：执行记录仍将“分别验证工具发现、参数拒绝、annotations、结构化错误、upload_dir indeterminate 告警且不整体重跑”保留为未完成项；最终证据只记录 Codex 的发现/参数拒绝/`max_bytes` 错误及 WorkBuddy 的发现/一个运行时错误/类型拒绝。annotations 被 FastMCP 探针覆盖，而非两个真实宿主分别覆盖；`upload_dir status=indeterminate` 只有工具描述和契约测试，没有两个真实宿主中 Agent 告警且不整体重跑的记录。
- 实际影响：不能证明两个正式支持宿主满足 Accepted Spec 的关键 Agent 可见行为，A37 和“完成正式宿主阻塞性验证”的通过标记与证据矛盾。
- 违反契约：Accepted Spec §5 的逐宿主验证要求及验收标准第 573 行；任一宿主不满足或未验证均应停止交付。
- 建议修复：在明确授权的正式 Codex、WorkBuddy 环境分别执行并记录完整矩阵，特别是 annotations 的宿主可见性、带 details 的 `isError=true`，以及可控产生 `upload_dir status=indeterminate` 后 Agent 的告警与不整体重跑行为。不要用框架探针替代真实宿主证据。
- 应补测试/证据：两个宿主各自的工具发现、调用前拒绝、annotations、结构化错误详情和 indeterminate 行为记录。若只补外部证据而实现与仓库内容不变，其本身不证明代码需改；但在证据完成前发布准备仍被阻断。

### P2-1：driver 仍可在业务错误中泄露真实远端 root

- 分类：既有问题，但属于本轮明确承诺解决的范围；非 P1 单独阻断，但必须随新 Candidate 修复。
- 位置：`src/ft_ftp_mcp_stdio/drivers/ftp.py:148`、`:158`、`:209`；`src/ft_ftp_mcp_stdio/drivers/sftp.py:145`、`:156`。这些行由 Start 之前的提交引入，但 Candidate 未收敛。
- 可触发场景：FTP `make_dir` 权限失败会把逐段真实路径 `current` 放入 `AppError.message`；下载在 service 首次检查后发生对象类型变化时，driver 再检查并把真实 `path` 写入错误；直接或后续复用 driver 的 overwrite 拒绝也含真实路径。
- 实际影响：Agent 可见结构化错误可能暴露配置 root 和服务器目录布局，破坏虚拟路径抽象及敏感字段 denylist。
- 违反契约：Accepted Spec §7 的“成功结果、业务错误、message/hint/details 不得包含真实 root”及验收标准第 543-545 行；ADR 0001 的反向映射/净化要求。
- 建议修复：driver 错误只返回无路径的稳定语义，或携带仅供内部映射的结构化上下文，由 service 映射成虚拟路径后再输出；禁止直接插入真实 driver path。
- 应补测试：正常权限失败和检查后对象类型变化两种路径，向配置注入独特 root/host/username 后扫描最终 `message`、`hint`、`details` 和批量 message。

### P2-2：显式配置指纹匹配时不会同步覆盖旧 known-hosts 记录

- 分类：Candidate 新引入的问题；契约偏差。
- 位置：`src/ft_ftp_mcp_stdio/known_hosts.py:22`-`:29`；相关不足测试为 `tests/test_known_hosts.py:19`-`:25`。
- 可触发场景：管理员显式更新 `host_key_fingerprint` 以信任已轮换的主机密钥，但同 alias 的 known-hosts 仍保存旧算法/指纹。远端密钥与显式配置完全匹配后，代码仍因旧 known-hosts 不匹配而拒绝；只有 known 为空时才写入。
- 实际影响：显式配置无法作为规范定义的信任依据完成合法密钥轮换，也不能把已验证指纹同步到独立状态，导致持续不可用。当前测试只覆盖空 known-hosts 的首次写入，没有覆盖旧记录更新。
- 违反契约：Accepted Spec §8.1 第 211-218 行；配置规范中“配置指纹匹配后同步到独立 known-hosts”的行为。
- 建议修复：当 `expected` 非空且与远端匹配时，以该显式信任为依据，在持锁状态下原子新增或更新 alias 记录；未提供 expected 时才按 TOFU 旧记录严格比较。
- 应补测试：旧记录到显式新指纹的原子更新、算法变化、远端不匹配不写入、写入失败保留旧完整文件、并发更新 fail-closed。

## 6. 问题分类汇总

| 类别 | Findings |
| --- | --- |
| Candidate 新引入的实现/契约问题 | P1-1、P1-2、P1-3、P2-2 |
| 既有但本轮承诺解决的问题 | P2-1 |
| 测试或证据缺口 | P1-2（同时为实现缺陷）、P1-4、P1-5 |
| 已接受残余风险，不作为 finding | FTP 无法可靠识别所有远端 symlink；SFTP 与本地逐段检查后的剩余 TOCTOU；配置 root 为 `/` 时依赖服务端隔离；ADR 0007 接受的首次目标检查后并发覆盖与临时名竞态；本地上传允许任意可读绝对路径；staging 无 TTL/配额 |

问题数量：P0 0 项，P1 5 项，P2 2 项，P3 0 项，共 7 项。最高严重级别为 P1。

## 7. 最终结论

**不通过，必须修复并创建新 Candidate。**

P1-1、P1-2、P1-3 是安全边界、数据完整性/不确定性契约的实现缺陷；P1-4 和 P1-5 是 Accepted Spec 明确规定为阻塞条件的证据缺口。不得仅修改执行清单的 A16、A37、A39、A40 状态来关闭问题。修复代码或测试后必须固定新 Candidate，并至少审查旧 Candidate 到新 Candidate 的增量；若修复改变核心安全设计或写恢复模型，应先回到 Spec/ADR 复审。

## 8. 实施者整改记录（不构成独立复审）

本节由实施者在首轮审查完成后追加，只记录修复与验证事实，不修改第 7 节的原始审查结论，也不把问题自行标记为独立审查通过。新 Candidate 固定后，仍须由独立 Agent 至少审查首个 Candidate 到整改 Candidate 的增量。

| Finding | 整改内容 | 回归与证据 | 实施状态 |
| --- | --- | --- | --- |
| P1-1 | SFTP 创建路径从配置 root 逐段 `lstat`，只允许已验证 root 以下的缺失后缀；`make_dir` 对既有段拒绝 symlink/非目录。FTP 创建前也逐段检查可枚举链接。 | SFTP root/中间/最终/断裂链接、权限/连接失败，以及 `make_dir`/`upload_dir` 写入前父链接拒绝测试。 | 已实现，待独立复审 |
| P1-2 | 写路径记录请求是否已发出；仅请求前连接失败允许一次重试。`make_dir`、upload、rename/move、delete 分别执行规范规定的后置核验；FTP `unique` 只用于 move/rename，upload 只接受可靠内容哈希，delete 发出后始终不重放。 | 六类写操作请求前断线、响应丢失、核验失败、并发替换，以及 SFTP、无 FTP unique、有 FTP unique 的 fake-driver 矩阵；新增真实 FTP driver 的 MLSD unique 缓存与重连刷新测试。 | 已实现，待独立复审 |
| P1-3 | FTP/SFTP `exists` 只把明确 `not_found` 作为不存在；临时名检查失败阻止上传，临时上传失败后使用新连接严格清理，清理状态不明报告可能残留。 | 临时名权限/连接失败、上传中断、清理检查失败和残留报告测试。 | 已实现，待独立复审 |
| P1-4 | symlink 跳过条件收窄为 Windows `WinError 1314`；新增真实 junction、断裂 junction、reparse point 属性和打开后句柄身份竞态覆盖。 | 非 live 为 `149 passed, 11 skipped`；唯一平台跳过是文件 symlink 权限，junction/reparse/身份测试实际通过。 | 证据已补，待独立复审 |
| P1-5 | 增加使用正式 server registry、Schema 和 annotations 的安全 host fixture，固定返回 `upload_dir status=indeterminate`，用于两个正式宿主验证告警与不整体重跑。 | Codex fixture 实调通过。WorkBuddy 仅调用一次并正确告警、不整体重跑；其模型侧看不到四种 annotations，具体丢失层级未经验证。ADR 0008 将 annotations 保证限定在服务端接口，并保留两个宿主的错误与 indeterminate 端到端门禁；第三次独立增量设计复审通过，项目负责人已确认。 | 整改完成，待独立代码复审 |
| P2-1 | driver 业务错误不再插入真实远端路径。 | FTP/SFTP 权限失败、目标类型变化和唯一 root 字符串扫描测试。 | 已实现，待独立复审 |
| P2-2 | 显式配置指纹与远端匹配后，在持锁原子写路径中新增或替换 alias 的陈旧 known-hosts；无显式指纹的 TOFU 冲突仍拒绝。 | 陈旧记录更新、算法变化、远端不匹配不写、写入失败保留旧文件测试。 | 已实现，待独立复审 |

整改验证：`uv run pytest -q -rs` 为 `149 passed, 11 skipped`；`uv run pytest -q --live -rs` 最终为 `159 passed, 1 skipped`；ruff、mypy（44 个源文件）、FastMCP 五项探针和 Schema 重导出无差异均通过。完整 live 后，FTP/SFTP 固定测试根和专用 staging 均已清理并只读复核。WorkBuddy 模型侧 annotations 不可见触发原 Accepted Spec 的返回门禁；项目负责人随后选择 ADR 0008 的责任边界。第三次独立增量设计复审 P0/P1/P2/P3 均为 0，ADR 0008 和 Spec 已于 2026-09-23 更新为 `Accepted`，允许继续固定整改 Candidate。

## 第二次独立代码复审（2026-09-23）

### 1. 结论与范围

**通过。未发现阻止 Candidate 通过的代码问题。** 本轮发现 1 项非阻断 P2 兼容性问题；该问题在异常场景中 fail-closed，不会绕过路径、只读、覆盖、主机密钥、上传限制或禁止盲目重放等强制规则，且有直接规避方式，因此接受其作为本 Candidate 的已知限制，不要求重新固定 Candidate。允许进入最终验收和发布准备。

- Start SHA：`1e816078458b41ea2a7518a8561aa6558ee2daf4`
- 上一版未通过 Candidate：`bdcf5ecd8076cecacc8551140104acb827dc200f`
- 本次整改 Candidate：`459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712`
- Candidate 记录提交：`9d3b040a54c2a4983e86757eb6fd8770a939b532`
- 正式整改增量：`git diff bdcf5ecd8076cecacc8551140104acb827dc200f 459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712`
- 完整实现范围：`git diff 1e816078458b41ea2a7518a8561aa6558ee2daf4 459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712`

复审开始时分支为 `feature/next-development`，HEAD 为 `9d3b040a54c2a4983e86757eb6fd8770a939b532`，工作区和暂存区均为空。四个移交 SHA 均为有效 commit；Start 是整改 Candidate 的祖先，Start 到整改 Candidate 共 16 个提交。`459f753` 的父提交为 `e771ce3`；`9d3b040` 直接基于 `459f753`，且只修改执行清单中的状态、整改 Candidate SHA 和复审范围记录，未改变实现或契约。

审查以固定提交中的 Accepted Spec、有效 ADR 0001、0002、0003、0006、0007、0008、执行清单、首轮代码审查、第三次独立增量设计复审和缺陷台账为依据。契约判断没有使用工作区内容代替固定 SHA。重点逐行复核了整改增量中的 `service.py`、FTP/SFTP driver、known-hosts、host fixture 及相应测试，并重新核对 Start 到整改 Candidate 的公开 Schema、配置、错误映射、路径边界和工具注册范围。

### 2. Findings

#### P2-1：本地文件系统根目录作为 `upload_dir` 源时触发未初始化变量

- 严重级别：P2，非阻断；本 Candidate 接受为已知兼容性限制。
- 文件和行号：`src/ft_ftp_mcp_stdio/service.py:731`、`:736`、`:743`。
- 可触发场景：调用 `upload_dir`，将当前平台文件系统根目录本身作为绝对 `local_path`，例如 Windows 的 `D:\\`。`_assert_plain_path` 从 `path.anchor` 开始，只在 `path.parts[1:]` 循环内赋值 `info`；根目录没有后续路径段，随后在第 743 行访问 `info.st_mode`，触发 `UnboundLocalError`。本轮用只读命令直接复现。
- 实际影响：该输入通过 MCP 层后被包装为稳定 `server_error`，因此合法的本地根目录不能作为批量上传源；错误类型也不能准确表达本地路径检查失败。流程在建立远端连接和读取文件之前失败，不会产生远端写入、信息泄露或安全边界绕过。用户可选择根目录下的具体子目录规避。
- 违反要求：Accepted Spec §7.2 将 `upload_dir.local_path` 定义为本机绝对路径并明确本轮不引入本地允许根白名单；§19 只把缺少允许根白名单列为已接受风险，没有排除文件系统根目录。当前实现额外形成了未声明的输入限制。
- 建议修复方向：在遍历子路径段前先对 `Path(path.anchor)` 执行 `lstat` 并初始化 `info`，继续应用 symlink/reparse 和目录类型检查；增加驱动器根或 POSIX `/` 的 `_validate_local_directory` 回归测试。修复可在后续维护版本完成。
- 接受判断：可接受。它是低频、可规避且 fail-closed 的功能兼容性问题，不影响 Candidate 的安全属性、远端数据完整性或公开结果结构，不阻塞 Spec 已有门禁或最终验收。

### 3. 上一轮 7 项问题关闭状态

| 上一轮 Finding | 本轮状态 | 独立复核结论 |
| --- | --- | --- |
| P1-1 SFTP 创建目录绕过逐段 `lstat` | **已关闭** | `make_dir` 和 `upload_dir` 在写前调用统一路径检查；SFTP 从 root 逐段 `lstat`，已存在链接、断裂链接及检查失败均 fail-closed，`make_dir` 自身也拒绝链接或非目录段。测试验证父链接场景不调用 `mkdir`。 |
| P1-2 写操作恢复矩阵未实现 | **已关闭** | `_WriteAttempt` 区分请求发出前后；仅请求前连接失败自动重试一次。`make_dir` 按明确不存在规则恢复，upload 仅可靠远端哈希匹配时恢复成功，rename/move 仅 FTP `unique` 强身份匹配时恢复，delete 发出后始终不重放并返回 `outcome_unknown`。批量单项不确定写入 `indeterminate`。 |
| P1-3 临时对象检查吞掉连接/权限错误 | **已关闭** | FTP/SFTP `exists` 只把明确 `not_found` 解释为不存在；其他错误向上传流程传播。失败上传使用新连接检查并清理精确临时路径，清理状态无法确认时返回说明可能残留的 `server_error`，不再伪装成安全跳过。 |
| P1-4 Windows symlink/junction/reparse 证据不足 | **已关闭** | 普通 symlink 只在 Windows `WinError 1314` 时跳过；真实 junction、断裂 junction、reparse 属性和打开后句柄身份不一致测试均存在。本机本轮仅普通文件 symlink 因权限跳过，其余相关测试实际通过。 |
| P1-5 正式宿主证据不足 | **已关闭** | ADR 0008 与重新 Accepted 的 Spec 已经独立设计复审通过。正式 Schema、MCP Client、能力探针和 Codex 模型侧证据覆盖 annotations；Codex/WorkBuddy 均有工具发现、参数拒绝、结构化错误及 fixture `status=indeterminate` 的识别、告警和禁止整体重跑证据。WorkBuddy 模型侧 annotations 不可见仍准确保留为宿主限制。 |
| P2-1 driver 错误泄露真实 root | **已关闭** | FTP/SFTP 业务错误不再拼接真实 driver path；权限失败、对象类型变化和敏感 root 扫描测试通过。异常映射继续只输出净化后的操作语义。 |
| P2-2 显式指纹不更新陈旧 known-hosts | **已关闭** | 显式指纹先验证远端值，再在锁内原子新增或替换 alias 记录；无显式指纹时仍严格拒绝 TOFU 冲突。陈旧记录、算法变化、不匹配不写和原子替换失败保留旧文件均有测试。 |

没有上一轮问题处于“部分关闭”“未关闭”或“被新问题取代”状态。本轮 P2-1 是独立发现，不替代上一轮任一问题。

### 4. 验证记录

| 命令/检查 | 结果 |
| --- | --- |
| 分支、HEAD、`git status --short`、四个 `git cat-file -t`、父子及祖先关系 | 通过；分支和提交关系符合移交，起始工作区干净 |
| `git diff --check Start Candidate` | 通过 |
| `uv run pytest -q -rs -p no:cacheprovider --basetemp=.../.pytest-temp/independent-code-review-20260923` | `149 passed, 11 skipped`；10 项因未传 `--live` 跳过，1 项因 Windows `WinError 1314` 跳过；没有运行 live 测试 |
| `uv run pytest -q tests/test_schema.py tests/test_contract_matrix.py tests/test_drivers.py tests/test_known_hosts.py tests/test_host_contract_fixture.py -p no:cacheprovider --basetemp=...` | `68 passed` |
| `uv run ruff check .` | 通过 |
| `uv run mypy src tests scripts` | 通过；44 个源文件 |
| `uv run python scripts/probe_mcp_contract.py` | 五项检查全部通过：根对象 `oneOf`、结构化运行时错误、title/annotations、枚举调用前拒绝、框架参数错误 null structured content |
| `uv run python -c "... _assert_plain_path(Path(Path.cwd().anchor), require_directory=True)"` | 复现本轮 P2-1：`UnboundLocalError`，位置为 `service.py:743` |

正式 Schema 未在本轮重写。`tests/test_schema.py` 已从运行时 `tools/list` 完整比较正式快照并通过，因此没有留下生成差异。本轮没有运行 FTP/SFTP live 测试、连接或修改远端服务器，也没有修改宿主配置、提交、推送、发布、合并、变基或打标签。

### 5. 残余风险与最终门禁

- P0：0 项。
- P1：0 项。
- P2：1 项，已在本节明确接受为非阻断兼容性限制。
- P3：0 项。
- 最高严重级别：P2。
- 总体结论：**通过**。
- 最终门禁：**允许进入最终验收和发布准备**。

仍需保留 Accepted Spec §19 已列风险，尤其是 WorkBuddy 模型侧 annotations 不可见、FTP 无法可靠识别全部 symlink、SFTP 与本地逐段检查后的 TOCTOU、ADR 0007 接受的并发覆盖/临时名竞态、本地上传无允许根白名单、批量资源无客户端总量限制，以及未知大小下载缺少一致快照证明。本轮没有重跑 live 或正式宿主验证；结论依赖固定 Candidate 中已记录且此前完成的授权 live 与真实宿主证据，并以本轮非 live 回归、契约探针和代码复核确认整改没有破坏这些证据对应的实现。

## 第三次独立增量代码复审：文件系统根目录修复（2026-09-23）

### 1. 结论、身份与审查范围

**通过。原 P2-1 已完整关闭，本轮没有新增 P0、P1、P2 或 P3 finding。** P2 修复 Candidate 可以进入最终验收和发布准备，不需要因本次复审创建新的实现 Candidate。

- 实际分支：`feature/next-development`。
- 实际 HEAD：`d83dce1708ba3051a9768a2e30f80eae33c36446`（`Record filesystem root fix candidate`）。
- 复审开始时工作区和暂存区均为空；`git status --short` 和 `git diff --cached --stat` 均无输出。
- Start SHA：`1e816078458b41ea2a7518a8561aa6558ee2daf4`。
- 上一版已通过但含 P2 的 Candidate：`459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712`。
- 第二次独立复审及缺陷登记提交：`92983a13ec7baab2b6f8ed4d1543dfaafef0e51f`。
- P2 修复 Candidate：`0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`。
- Candidate 记录提交及当前 HEAD：`d83dce1708ba3051a9768a2e30f80eae33c36446`。

上述五个 SHA 均经 `git cat-file -t` 确认为 commit。`0747d2b` 是 `d83dce1` 的直接父提交，`git merge-base --is-ancestor 0747d2b HEAD` 通过。对 `0747d2b..d83dce1` 的核验显示仅 `docs/development/plans/next-development.md` 发生变化，内容限于固定 P2 Candidate、记录离线验证结果、说明未重跑 live 的理由和更新审查清单；`src`、`tests`、Spec、ADR、Schema 均无变化，因此该记录提交没有改变实现或契约。

实际审查范围为：

- 修复增量：`git diff 459f7534f7d6a3d7ec2b2e03c7be07a77f4ae712 0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`。该范围修改 5 个文件，净增 125 行、删除 3 行；其中实现仅为 `service.py` 的 3 行根路径检查，测试新增 34 行，其余是第二次复审、`BUG-011` 和执行证据记录。
- 完整实现范围：`git diff 1e816078458b41ea2a7518a8561aa6558ee2daf4 0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1`。核对了完整 name/status、stat、`diff --check`、既有第二次复审关闭项及本次修复与 `upload_dir`、driver 创建、错误映射、Schema/契约的交互；没有发现本次 3 行实现令完整 Candidate 中既有行为失配。
- 两个范围的 `git diff --check` 均通过。

审查依据包括第二次独立复审 P2-1、`BUG-011`、Accepted Spec §7.2、§17、§19、执行清单以及有效 ADR 0006。本轮没有使用 HEAD 之后的未提交实现作为 Candidate 证据。

### 2. 原 P2-1 关闭状态

状态：**已关闭**。

`src/ft_ftp_mcp_stdio/service.py:731` 的 `_assert_plain_path` 现在先构造 `Path(path.anchor)`，在 `service.py:736` 对根路径自身执行 `lstat`，并在 `service.py:737`-`:738` 应用既有 symlink/reparse point 拒绝规则；之后才从 `path.parts[1:]` 逐段检查子路径。最终对象仍在 `service.py:746`-`:749` 按调用要求验证为目录或普通文件。

独立路径分解检查确认：Windows 驱动器根 `D:\\`、UNC share 根 `\\\\server\\share\\` 和 POSIX `/` 的 `parts[1:]` 都为空，`anchor` 分别保留完整根；普通子路径只把根之后的段放入 `parts[1:]`。因此根路径只检查一次，普通文件和普通子目录仍按根到最终对象逐段检查，没有跳段或重复拼接。

异常边界保持不变：根或任一段 `lstat` 的 `FileNotFoundError` 仍映射为 `not_found`；最终对象类型不符仍映射为 `not_found`；symlink/reparse point 仍为 `symlink_unsupported`；其他异常继续沿用既有上层异常映射。`upload_dir` 在 `service.py:518` 完成本地目录预检，首次 driver 创建只能在 `service.py:588` 进入 `_run_write` 后发生，因此本地预检失败确定早于凭据读取、driver 创建和远端连接。

测试具有修复前失败能力：`tests/test_service.py:344` 的当前平台根目录测试在旧实现中会因循环不执行而直接触发 `UnboundLocalError`，在新实现中验证合法根目录被接受；`:350` 验证根对象类型；`:363` 验证根路径缺失返回 `not_found` 且 driver factory 不得调用。既有普通文件、普通子目录、Windows junction/reparse point、文件 symlink、打开后身份变化和常规上传测试继续覆盖非根路径回归。当前 Windows 运行实际覆盖驱动器根；UNC 根与 POSIX `/` 的等价分解由 `pathlib` 语义和本次只读分解检查确认，代码不包含按根类型分支。

### 3. Findings

未发现 P0、P1、P2 或 P3 问题。

`BUG-011` 在固定 Candidate 台账中的状态为 `Fixed`，与其定义的“实现和相关测试已完成，尚待独立验证”及候审时点一致；本次独立复审已提供验证结论，可在后续最终验收的治理记录更新中转为 `Verified`。因本任务只允许修改本报告，本轮未越权改写缺陷台账或执行清单。这不要求改变实现 Candidate。

### 4. 实际验证

| 命令/检查 | 结果 |
| --- | --- |
| 分支、HEAD、`git status --short`、暂存区、五个 SHA、父子与祖先关系 | 通过；身份和提交关系与移交一致，起始工作区干净 |
| `git diff --check 459f753... 0747d2b...` | 通过 |
| `git diff --check 1e81607... 0747d2b...` | 通过 |
| `uv run pytest -q -rs` | 首次运行因沙箱拒绝访问系统 pytest 临时目录而在 fixture setup 阶段产生环境错误，未形成代码测试结论；未运行 live |
| `uv run --no-sync pytest -q -rs -p no:cacheprovider --basetemp=.../independent-root-review-full` | `152 passed, 11 skipped`；10 项因未启用 `--live`，1 项因 Windows 创建文件 symlink 返回 `WinError 1314` |
| `uv run --no-sync pytest -q tests/test_service.py -rs -p no:cacheprovider --basetemp=.../independent-root-review-service` | `23 passed, 1 skipped`；唯一 skip 为上述 Windows 文件 symlink 权限 |
| `uv run ruff check .` | 通过 |
| `uv run mypy src tests scripts` | 通过；44 个源文件 |
| `uv run python scripts/probe_mcp_contract.py` | 五项全部通过：根对象 `oneOf`、结构化运行时错误、title/annotations、枚举调用前拒绝、框架参数错误 null structured content |
| `pathlib` 驱动器根、UNC 根、POSIX 根及子路径分解检查 | 通过；三类根的 `parts[1:]` 均为空，子路径保留根后的组件 |

没有重导出或修改正式 Schema；全量测试包含运行时 Schema 快照比较并通过，复审结束前检查确认 `docs/schema/mcp-tools.json` 无差异。本轮没有运行 FTP/SFTP live 测试、创建远端 driver、读取凭据或操作远端对象。

### 5. Live 重跑判断

本次不重跑 FTP/SFTP live 矩阵是合理的，不是直接采信执行清单结论。修复只在本地 `_assert_plain_path` 增加根路径的 `lstat` 和既有链接属性检查；`upload_dir` 的该预检位于 `_run_write` 及 driver 创建之前。增量没有修改 FTP/SFTP driver、远端路径映射、连接/认证、传输、提交、恢复、清理、公开 MCP 参数、Schema 或结果结构。离线全量与 service 专项已同时覆盖修复分支和远端调用前边界。因此既有整改 Candidate 的 `159 passed, 1 skipped` live 证据仍适用于未变化的远端行为；为这 3 行纯本地预检重复执行有远端副作用的完整 live 写入矩阵不能提供相称的新增信心。

### 6. 数量与最终门禁

- P0：0 项。
- P1：0 项。
- P2：0 项。
- P3：0 项。
- 最高严重级别：无。
- 总体结论：**通过**。
- 是否需要新 Candidate：**不需要**。
- 最终门禁：**允许 P2 修复 Candidate `0747d2b66d1cc242452e85d1b1fca4ff4b6e11a1` 进入最终验收和发布准备**。
