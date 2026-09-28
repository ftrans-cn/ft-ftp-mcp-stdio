# 下一轮研发变更 Spec：MCP 契约、安全边界与服务器发现

> 状态：Implemented
> 创建日期：2026-09-20
> 最近修订日期：2026-09-23
> 上次接受日期：2026-09-22；本次重新接受日期：2026-09-23
> 实现完成日期：2026-09-23
> 基于：`docs/spec/current.md`
> 风险等级：高影响
> 关联缺陷：`BUG-001`、`BUG-002`、`BUG-004`、`BUG-006`、`BUG-008`、`BUG-009`、`BUG-010`、`BUG-011`

## 1. 背景与目标

当前服务存在工具语义、输入输出契约、错误表达、连接信息暴露、路径隔离和危险操作重试等问题。

本轮目标：

- 完善服务、工具和参数的语义化描述；
- 增加精确 `inputSchema`、`outputSchema` 和 MCP annotations；
- 增加安全的服务器发现工具 `list_servers`；
- 最小化连接、配置、凭据和底层协议信息暴露；
- 引入 Agent 可见的虚拟远程根路径；
- 将服务器缺省模式调整为只读；
- 修正错误、重试、批量结果和时间字段契约；
- 修复本轮已规划缺陷；
- 完成正式 MCP Schema 的权威来源迁移。

## 2. 范围

本轮包含：

- 服务 instructions、工具描述、字段描述和中文 title；
- `list_servers` 工具及服务器可选 `description` 配置；
- 工具标准 annotations；
- 精确输入、成功和错误输出 Schema；
- 工具执行错误 `isError=true`；
- 对外失败统一 `retryable=false`；
- SFTP 不存在对象的错误映射；
- 写操作结果核验和禁止盲目重放；
- 虚拟远程路径和 root 保护；
- 不解析、不跟随符号链接的拒绝策略；
- `readOnly=true` 安全默认值；
- `test_connection` 输出收敛；
- 对 `upload_file` 和 `upload_dir` 中每个文件统一生效的上传文件大小限制；
- 文本预览边界行为；
- FTP/SFTP `mtime` 格式统一；
- 批量逐项处理和部分成功的结构化表达。

以上事项作为一个统一研发范围交付，不拆分为多个研发批次或版本。实现可以按依赖关系拆分提交和安排先后顺序，但所有范围内事项均完成并通过统一验收后，本轮才视为完成。

## 3. 非范围

本轮不包含：

- 本地上传允许根目录或本地路径白名单；
- `BUG-007` 的 `search_files` 兼容性修复，待复现；
- `INV-001` 的结论性修复，待定位；
- Windows 非法下载文件名的最终转换策略；
- staging TTL、配额和自动清理；
- 全局频率限制、异步任务和断点续传；
- 服务端总执行超时和取消协作机制；
- 远端内容 Prompt Injection 检测；
- 安装提示精简、升级和卸载流程。

本地上传路径仍可指向进程有权读取的任意绝对路径。该风险必须继续记录，不得宣称本轮已解决本地数据外传边界。

## 4. 服务身份与描述

服务名保持 `ft-ftp-mcp-stdio`，服务版本必须与产品包版本一致。

服务 instructions：

> 在已配置的 FTP/SFTP 服务器范围内浏览、读取、传输和管理文件。所有远程路径均为以 `/` 开头的虚拟绝对路径，并受服务器 root 限制。凭据由本地安全配置读取，不得要求用户在 MCP 会话中提供密码、私钥或口令。写入、覆盖、移动和删除必须遵守工具 Schema、只读策略及客户端确认要求。

工具描述只说明用途、使用时机、主要副作用和相邻工具差异。参数格式进入字段 Schema，返回字段进入 `outputSchema`，风险进入 annotations，强制规则由代码执行。所有工具 title 和 description 必须为非空字符串，并作为正式 Schema 快照的一部分进行完整比较；不得包含 host、port、username、真实 root、key path、fingerprint 或凭据来源等禁止信息。title 不要求全局唯一，本轮不另设任意长度上限；语义准确性由设计与代码审查确认。

## 5. 正式 Schema 治理

- `docs/schema/mcp-tools.json` 是唯一正式的机器可读工具契约。
- 正式 Schema 从运行时 `tools/list` 生成，不直接手工编辑。
- `docs/MCP工具Schema草案_v0.3.md` 及更早草案退出当前事实来源。
- 不提供历史 Schema 并行维护期。
- Schema 测试必须完整比较运行时结果与正式快照。
- 服务版本、annotations 和 MCP 线级 `isError` 另设契约测试。
- 当前契约行为基线为锁文件中的 FastMCP 4.0.2；每次调整 FastMCP 或 MCP SDK 版本时，必须重新运行最小参数与输出契约测试。
- 本轮正式支持的 MCP 宿主仅为 Codex 和 WorkBuddy。服务端必须在标准 `tools/list` 中发送准确 annotations，并由正式 Schema、MCP Client 测试、框架能力探针和至少一个真实宿主的模型侧端到端验证共同证明；本轮由 Codex 提供真实宿主端到端证据。每个其他正式宿主必须能够接受带 annotations 的工具清单并继续正常发现和调用工具，但项目不保证第三方宿主会消费、展示或向模型透传 annotations。交付前仍必须分别在 Codex 和 WorkBuddy 中验证工具发现、调用前参数拒绝，以及 `isError=true` 时 Agent 能取得稳定 `error_type` 和契约要求的结构化详情；不要求宿主 UI 原样展示底层 `structuredContent`，但模型侧必须可靠获得这些错误信息。两个宿主还必须分别识别 `upload_dir status=indeterminate`、向用户告警且不整体重试。任一宿主不满足这些强制端到端条件时必须停止交付并退回本 Spec 决定兼容方案，不得静默降级或只登记为一般残余风险。具体取舍见 ADR 0008。

## 6. 新增 `list_servers`

用途：用户未明确指定服务器、使用模糊称呼或存在多个候选时，列出可选择的逻辑服务器。

该工具只读本地配置，不连接 FTP/SFTP，不读取凭据，不触发 TOFU。

工具描述：

> 列出当前配置中可供 MCP 文件工具使用的逻辑服务器。返回服务器别名、可选说明、协议、只读状态和默认标记；不返回地址、端口、用户名、真实 root 或凭据信息。当用户未明确指定服务器且存在多个候选时，先调用本工具，再根据候选请用户确认。

无业务输入：

```json
{
  "type": "object",
  "additionalProperties": false
}
```

成功输出：

```json
{
  "ok": true,
  "servers": [
    {
      "alias": "finance_prod",
      "description": "财务生产报表服务器",
      "protocol": "sftp",
      "read_only": true,
      "is_default": true
    }
  ]
}
```

禁止返回 `host`、`port`、`username`、`root`、`banner`、`key_path`、`fingerprint`、`credential_env` 和 `credential_source`。

服务器配置增加可选 `description`：非空字符串，最长 200 个字符，仅用于用户展示和 Agent 选择，不得包含秘密。`doctor` 应对疑似 IP、`host:port`、`user@host`、绝对路径、密钥文件名等内容给出安全告警；该告警不阻止配置加载，配置内容的最终责任仍由用户承担。

未知 alias 错误不得枚举全部服务器，应建议调用 `list_servers`。配置加载必须区分“默认配置路径下文件不存在”“合法配置”和“文件存在但不可读或非法”三种状态：仅当没有设置 `FT_FTP_MCP_CONFIG` 且默认配置文件不存在时，`list_servers` 返回空列表，不将其作为工具执行错误；显式环境变量指向的文件不存在，以及文件不可读、JSON 损坏、版本错误、`servers` 为空或不符合 Schema 时，均返回 `invalid_config`。除 `list_servers` 外的工具在无可用服务器时返回 `invalid_config`，不得通过捕获一般配置错误把非法配置伪装成空配置。

## 7. 虚拟远程路径

所有表示远程对象的 `path`、`remote_path`、`from_path` 和 `to_path` 均为虚拟绝对路径：

- `/` 表示配置 root；
- `/reports/a.csv` 表示 root 下的 `reports/a.csv`；
- Agent 不得看到或传入真实服务器 root；
- 成功结果、业务错误和 Agent 可见日志中的远程路径只使用虚拟路径。

本规则不把本机路径伪装为虚拟远程路径。`download_file.local_path`、`download_dir.local_dir` 继续使用本机绝对路径语义；第 11.5 节规定的 `upload_dir` 批量明细使用相对于本次 `local_path` 的本机源相对路径。

若配置 root 为 `/srv/finance`，则 `/` 映射为 `/srv/finance`，`/reports/a.csv` 映射为 `/srv/finance/reports/a.csv`。

映射流程：

1. 校验虚拟路径以 `/` 开头；
2. 拒绝空路径、反斜杠、NUL 和完整 `..` 段；
3. 规范化 `.` 段；
4. 在服务内部拼接真实 root；
5. 再次验证映射结果位于 root 内。

驱动返回的 `FileInfo.path`、目录项、搜索结果、下载批量失败项和异常上下文，在进入业务结果前必须统一执行真实路径到虚拟路径的反向映射。无法安全反向映射的远程路径不得原样输出，应使用稳定错误码和净化后的通用消息。成功结果、错误对象的 `message`、`hint`、`details` 以及批量明细均不得包含真实服务器 root。

FTP/SFTP 返回的目录项名称是不可信输入。递归搜索和下载在把名称用于远程子路径或本机目标前，必须拒绝空名称、`.`、`..`、NUL、`/`、`\`、绝对路径前缀、Windows 盘符或 UNC 前缀；远程子路径只能由已验证的单个名称组件构造。下载到本机时还必须拒绝目标平台无法安全创建的保留名称或非法名称，不做自动改名或转义。每次构造本地目标后必须规范化并二次验证其仍位于本次随机 staging 根目录内。

`download_dir` 遇到非法目录项时不得进入或落盘，将该项按对应虚拟远程路径写入 `failed`，`error_type=invalid_path`，并继续处理其他可安全定位的条目；若连安全虚拟路径都无法构造，则使用当前已验证父目录作为定位上下文，不回显原始恶意名称。`download_file` 的最终名称无法安全落盘时返回工具级 `invalid_path`。`list_dir` 或 `search_files` 遇到此类目录项时返回工具级 `invalid_path`，不得原样返回非法名称，也不得继续递归进入该条目。

传入真实服务器完整路径不会获得特殊待遇，只会被解释为虚拟 root 下的普通路径。

配置 `root` 改为必填；显式 `/` 合法，但 doctor 必须提示其依赖服务端 chroot、虚拟根或受限账号。

禁止对虚拟 `/` 执行：

- `delete`；
- `rename`；
- `move` 的源路径；
- 将其他对象移动为 `/`。

### 7.1 符号链接策略

本产品不支持通过符号链接访问或操作文件和目录。无论链接目标位于配置 root 内、root 外、无法访问或已经断裂，均不得解析或跟随链接目标，也不得以目标仍在 root 内为理由放行。长期决策及当前协议范围见 [ADR 0006](../../decisions/0006-reject-symbolic-link-access-across-supported-protocols.md)。

SFTP 对所有带远程路径的工具执行以下规则：

- 在发起目标业务操作前，从配置 root 开始按顺序对每个既有路径段执行不跟随最终链接的 `lstat`；一旦发现某段为符号链接，立即停止，不再检查或解析其目标；
- 禁止使用 `readlink` 获取目标，也不得以 `realpath` 解析链接后的位置作为授权依据；
- 配置 root 本身或到达配置 root 的任一可见路径段是符号链接时，该服务器配置无效，返回 `invalid_config`；
- 单对象工具的输入路径、源路径或目标路径经过符号链接，或者最终对象本身是符号链接时，返回 `symlink_unsupported`；不得读取、下载、覆盖、删除、重命名或移动链接本身；
- `list_dir` 的输入目录不得是或经过符号链接，但列出普通目录时可以返回其中的链接条目，固定使用 `type:symlink`；该条目的 `size`、`mtime` 只能来自不跟随链接的属性，禁止返回目标路径或目标属性；
- `search_files` 不进入符号链接目录，不返回链接本身或其目标中的匹配项；
- `download_dir` 遇到远端符号链接时不进入、不下载，将该项写入 `skipped`，`reason_type=symlink_unsupported`，继续处理其他条目；
- `upload_dir` 遇到本地源符号链接，或可确定的远端既有路径段或最终对象为符号链接时，不读取、不覆盖该链接，将对应项写入 `skipped`，`reason_type=symlink_unsupported`，继续处理其他条目；若批量调用的根输入路径本身是或经过符号链接，则在批量工作流开始前返回工具级 `symlink_unsupported`。

SFTP 的逐段 `lstat` 是强制安全检查，不允许在服务端不支持、返回结果不完整或检查结果不确定时降级继续。能够明确分类为对象不存在、权限不足或连接失败时，分别按 `not_found`、`permission_denied` 或连接类错误返回；其他无法完成可靠检查的情况在业务操作前返回净化后的 `server_error`。

上述检查不消除检查与实际操作之间的 TOCTOU，可靠安全边界仍依赖服务端 chroot、虚拟根、账号权限和操作系统权限。

FTP 使用相同策略，但协议通常不能可靠识别每个路径段的文件系统符号链接。只要服务器元数据或驱动能够明确识别 `symlink`，就必须按上述规则拒绝或跳过；无法可靠识别时不得宣称已经完成符号链接安全检查，隔离依赖服务器端边界。本轮不支持 FTPS，不得把 FTPS 写入协议枚举、实现范围或验收范围。

服务器管理员显式配置的虚拟目录或路径映射不属于符号链接。Serv-U Virtual Path 等服务器侧映射在服务器授权规则允许时作为普通目录处理；客户端不得把该类映射误判为符号链接。

### 7.2 本地上传路径与链接

`upload_file` 和 `upload_dir` 的本地源路径同样不得通过符号链接、Windows junction 或其他 reparse point 访问。实现必须检查上传根、每个既有中间路径段和最终文件；`upload_dir` 枚举时检查一次，每个文件打开前再次检查，并在读取任何字节前通过打开后的文件句柄复核对象身份和普通文件类型。检查结果表明对象被替换、身份不一致或平台无法可靠完成所需检查时必须 fail-closed，不得读取或上传该对象。

单文件调用检测到链接或 reparse point 时返回 `symlink_unsupported`。批量根路径存在此类对象时返回工具级 `symlink_unsupported`；批量中的单个条目存在此类对象时写入 `skipped`，`reason_type=symlink_unsupported`，并继续处理其他条目。检查本身失败且不能明确分类时返回净化后的 `server_error` 或批量失败项，不得在消息中披露链接目标或上传根之外的本机路径。

## 8. 配置安全默认值

- 配置格式版本调整为 `version:2`，新版本只接受版本 2 配置。
- 本轮以全新用户和全新配置为产品前提，不提供 `version:1` 到 `version:2` 的自动迁移、交互迁移、备份恢复或回滚兼容能力。
- setup 在没有现有配置时直接创建符合版本 2 契约的新配置。遇到其他配置版本时返回 `invalid_config`，不得自动迁移或覆盖现有配置；错误必须明确提示用户先自行备份并显式删除或替换旧配置，再重新运行 setup。
- `readOnly` 缺省值由 `false` 改为 `true`。
- 只有显式配置 `"readOnly": false` 才启用写操作。
- setup 必须准确展示安全默认值、必填 root 和可选 description。
- 能在当前字段或字段组确定的错误应即时报告。
- 写操作的只读拒绝必须发生在建立远端连接前。
- 服务器配置保留 `max_file_size_bytes`，但其语义调整为单个上传文件的大小上限，仅适用于 `upload_file` 和 `upload_dir`；默认值保持 2 GiB，允许配置为非负整数，`0` 表示不限制。
- 配置版本 2 删除 `max_batch_files` 和 `max_batch_total_bytes`。上传和下载均不设置客户端文件数量上限或批次总字节上限，下载也不受 `max_file_size_bytes` 限制。

### 8.1 SFTP 主机密钥信任

SFTP 保持现有“配置指纹强校验 + 独立 known-hosts/TOFU”模式，不把首次学习到的主机密钥回写到配置文件：

- 配置显式提供主机密钥指纹时，以配置指纹为信任依据；不匹配时立即终止连接，匹配后将经过验证的指纹同步到独立 known-hosts 状态；
- 配置未提供指纹时，使用独立 known-hosts 状态执行 TOFU。首次连接记录服务器主机密钥，后续连接必须与已记录值匹配；
- 配置指纹比较、known-hosts 比较或首次 TOFU 信任决定必须在发送密码、私钥签名或其他用户认证材料之前完成；校验失败时不得尝试用户认证；
- known-hosts 以服务器 alias 作为稳定身份键，并保存主机密钥算法和指纹；同一 alias 出现重复或相互冲突记录时必须 fail-closed，不得选择任意一条继续；
- known-hosts 必须采用同目录临时文件、落盘后原子替换和跨进程互斥的方式持久化，并在操作系统能力允许时限制为当前用户可读写；避免部分写入、并发覆盖或其他本机用户篡改；
- known-hosts 不可读、格式损坏、无法可靠加锁、无法安全持久化或权限不满足最低要求时必须 fail-closed，通过净化错误和 doctor 诊断，不得静默重建、覆盖或绕过；
- TOFU 状态是持久化环境变更。任何可能连接 SFTP 并在首次连接时写入该状态的工具，其 `readOnlyHint` 必须为 `false`；工具描述应披露这一可能副作用。

## 9. 工具 Annotations

| 工具 | `readOnlyHint` | `destructiveHint` | `idempotentHint` | `openWorldHint` |
| --- | ---: | ---: | ---: | ---: |
| `list_servers` | true | false | true | false |
| `list_dir`、`search_files`、`get_file_info`、`read_text_preview` | false | false | true | true |
| `test_connection` | false | false | true | true |
| `download_file`、`download_dir` | false | false | false | true |
| `make_dir` | false | false | true | true |
| `upload_file`、`upload_dir` | false | true | false | true |
| `rename`、`move`、`delete` | false | true | false | true |

Annotations 按工具可能产生的实际环境变更判断。使用日志、服务器访问日志、缓存和 atime 等一般附带状态不改变业务只读判断，但 known-hosts/TOFU 是后续连接必须依赖的持久化信任状态，不能排除在 `readOnlyHint` 之外。因此只有不建立 FTP/SFTP 连接、不触发 TOFU 的 `list_servers` 保持 `readOnlyHint=true`；其他工具可能因首次 SFTP 连接写入 TOFU 状态，统一设置为 `false`。`readOnlyHint=false` 不表示读取工具会修改远端业务数据。`rename`、`move`、`delete` 在响应丢失、并发重建或目标替换场景下不能安全地以相同参数重试，因此 `idempotentHint=false`。Annotations 仅为客户端提示，不是安全控制，也不直接决定内部重试。

## 10. 输入契约

- 所有参数增加字段级 description。
- 所有根 Schema 保持 `additionalProperties:false`。
- 路径统一描述为“服务器虚拟绝对路径”。
- `overwrite` 默认 `false`。
- `delete.confirm` 在 inputSchema 中声明为必填 boolean，不使用 `const:true` 或 `Literal[True]` 触发框架调用前拒绝；`confirm == true` 由工具运行时校验，失败时返回统一 `policy_rejected`。它是参数门控，不证明人工审批。
- `max_bytes` 必须为整数，业务允许范围为 1–1048576。inputSchema 不设置 `minimum`、`maximum` 等会触发调用前拒绝的范围关键字；范围由工具运行时校验，超出固定允许范围时返回 `policy_rejected`，不再静默钳制。
- `pattern` 在 inputSchema 中只声明为 string；非空且不得包含 `/` 或 `\` 的规则由工具运行时校验，失败时返回统一 `invalid_argument`。

参数校验按以下边界分层：

| 约束 | 校验层 | 对外结果 |
| --- | --- | --- |
| 缺少必填字段、字段类型错误、未知字段 | FastMCP / JSON Schema | `isError=true`、`structuredContent=null` 的框架工具错误 |
| 固定枚举，如 `protocol` | FastMCP / JSON Schema | `isError=true`、`structuredContent=null` 的框架工具错误 |
| `max_bytes` 的数值范围 | 工具运行时 | `isError=true` 的统一结构化错误 |
| `confirm == true`、`pattern` 非空且不含路径分隔符 | 工具运行时 | `isError=true` 的统一结构化错误 |
| 与服务器配置相关的动态上限 | 工具运行时 | `isError=true` 的统一结构化错误 |
| root、只读、覆盖、对象状态等业务规则 | 工具运行时 | `isError=true` 的统一结构化错误 |

需要返回统一业务错误体的约束不得写入会被 FastMCP 调用前执行的 JSON Schema 校验关键字。此类字段在 inputSchema 中只声明基础类型，并在 description 中说明业务范围；实际范围由工具运行时校验。框架参数错误是 FastMCP 包装的 MCP 工具错误结果，不是项目统一业务错误，也不是普通 JSON-RPC `invalid params` 响应。框架参数错误与工具运行时错误必须分别进行 MCP 线级契约测试。

## 11. 输出最小化

### 11.1 连接和服务器发现

`test_connection` 仅返回 `ok`、`server`、`protocol`、`read_only`，删除 `host`、`banner`、`username`、`root` 和 `credential_source`。

`list_servers` 只返回第 6 节定义的逻辑摘要。

### 11.2 浏览和信息工具

- `list_dir` entry 保留 `name`、`type`、`size`、`mtime`；删除 `perms`、`total_count`、`returned_count` 和说明性 `hint`，使用 `truncated` 表达截断。
- `search_files` 保留 `matches`、`truncated`；删除 `total_matches` 和 `returned_count`。
- `get_file_info` 保留 `path`、`type`、`size`、`mtime`，删除 `perms`。

### 11.3 传输和变更工具

- `download_file` 暂时保留 staging 内的 `local_path`。
- `upload_file` 删除可能被误解为远端校验的 `sha256`。
- `make_dir.created` 改为布尔值，不返回真实中间目录。
- `rename`、`move`、`delete` 只返回虚拟路径、对象类型和操作状态。

### 11.4 文本预览

`read_text_preview` 返回 `path`、`content`、`encoding`、`truncated`、`returned_lines`、`total_lines`、`partial_line`。

`encoding` 仅允许 `utf-8`、`utf-8-sig` 和 `gbk`；检测到 UTF-8 BOM 时移除 BOM，并返回 `utf-8-sig`。

截断必须发生在完整解码字符边界，而不是任意字节边界。若返回的最后一行仅为片段，该片段计入 `returned_lines`，并设置 `partial_line=true`；只要 `truncated=true`，`total_lines` 必须为 `null`。当 `max_bytes` 小于首个完整字符的编码长度时，允许 `content` 为空，但必须同时返回 `truncated=true` 和 `partial_line=true`，不得将其表达为文件为空。

### 11.5 批量工具

`download_dir` 增加 `status: complete | partial | failed`；`upload_dir` 增加 `status: complete | partial | failed | indeterminate`。

批量明细的 `path` 按工具固定语义，不允许调用方猜测路径属于本机还是远端：

- `upload_dir.skipped`、`upload_dir.failed` 和 `upload_dir.indeterminate` 使用相对于本次调用 `local_path` 的规范化相对路径；
- `download_dir.skipped` 和 `download_dir.failed` 使用服务器虚拟绝对路径；
- 跳过项使用稳定原因码，失败项使用稳定错误码，不直接返回底层异常文本。

上传相对路径统一使用 `/` 分隔，不以 `/` 开头，不包含盘符、UNC 前缀、空段、`.` 或 `..` 段，并且必须能够解析为本次上传根目录内的条目。批量明细不得返回上传根目录本身或根目录之外的本机路径。

状态映射如下：

- `complete`：全部目标均成功，且 `skipped`、`failed` 为空；对于 `upload_dir`，`indeterminate` 也必须为空。合法空目录返回 `complete`，并保留或创建对应根目录；
- `partial`：至少一项成功，同时存在已确定的跳过或失败项；对于 `upload_dir`，`indeterminate` 必须为空；
- `failed`：没有成功项，至少存在一个已确定的跳过或失败项；对于 `upload_dir`，`indeterminate` 必须为空；
- `indeterminate`：仅适用于 `upload_dir`，其 `indeterminate` 数组至少包含一项，不论其他项是否成功、跳过或失败。

批量成功结构中的 `ok:true` 仅表示工具完成了工作流并返回可解析的批量结果，不表示每个文件均成功。`upload_dir` 的 `status:indeterminate` 仍使用 `isError=false`、`ok:true`，具体不确定项通过 `indeterminate` 数组承载；调用前预检失败、整个批量工作流无法开始或无法生成可靠明细时，才返回 `isError=true` 的统一错误。`download_dir` 不使用 `outcome_unknown`、`indeterminate` 数组或 `status:indeterminate`。全部跳过且没有成功项时返回 `failed`；合法空目录与“全部条目被跳过”必须区别处理。

`upload_dir` 的工具描述必须明确 `ok:true` 不等于全部文件成功，调用方必须检查 `status`、`failed` 和 `indeterminate`。当 `status=indeterminate` 时，Agent 必须向用户说明具体不确定项并停止自动重试整个批次；只能在用户核验远端状态后，对明确需要重试的单项发起新调用。

### 11.6 时间格式

所有公开 `mtime` 统一为 ISO 8601 UTC 字符串并以 `Z` 结尾，来源规则固定如下：

| 来源 | 公开结果 |
| --- | --- |
| FTP `MLSD` 的合法 `modify` 值 | 按协议 UTC 语义解析并输出带 `Z` 的 ISO 8601；支持合法小数秒 |
| FTP `MDTM` 的合法响应 | 按协议 UTC 语义解析并输出带 `Z` 的 ISO 8601 |
| FTP `LIST` | 返回 `null`，不得根据进程时区、客户端时区或服务器地址猜测时区 |
| SFTP 合法 Unix 时间戳 | 按 UTC 转换并输出带 `Z` 的 ISO 8601 |
| 缺失、非法、越界或与已知协议语义矛盾的值 | 返回 `null` |

实现不得把未知时区伪装为 UTC，也不得对 FTP `LIST` 时间执行本地时区到 UTC 的推测性换算。协议原始时间仅进入受保护诊断日志。

### 11.7 规范性成功输出契约

所有成功输出对象均为封闭对象：列出的字段全部必填，`additionalProperties:false`。除表中特别说明外，字符串均为非空字符串，计数和大小均为大于等于 0 的整数。`read_text_preview.content` 允许为空字符串，但必须结合 `truncated`、`partial_line` 和文件状态解释，不得仅凭空字符串认定远端文件为空。

共享类型：

- `protocol`：`ftp | sftp`；
- `object_type`：`file | dir | symlink | other`；
- `mtime`：以 `Z` 结尾的 ISO 8601 UTC 字符串或 `null`；
- `entry`：`{name:string, type:object_type, size:integer|null, mtime:mtime}`；
- `match`：`{path:string, type:object_type, size:integer|null, mtime:mtime}`，其中 `path` 为虚拟路径；
- `batch_skip_reason`：`symlink_unsupported | size_limit_exceeded`；其中 `size_limit_exceeded` 仅适用于 `upload_dir`；
- `upload_limit_details`：`{limit_kind:upload_file_bytes, configured_limit:integer, observed_value:integer, observation:exact|at_least, remote_committed:false}`；`configured_limit >= 1`、`observed_value > configured_limit`；
- `batch_skipped` 是按 `reason_type` 区分的封闭联合：`symlink_unsupported` 变体为 `{path:string, reason_type:symlink_unsupported, message:string}`；`size_limit_exceeded` 变体为 `{path:string, reason_type:size_limit_exceeded, message:string, details:upload_limit_details}`；批量流式超限固定使用 `observation:at_least`；
- `batch_failed`：`{path:string, error_type:batch_error_type, message:string}`；
- `batch_error_type`：`not_found | invalid_path | policy_rejected | permission_denied | connection_unavailable | integrity_check_failed | server_error`；上传文件超限属于 `skipped`，不再作为 `batch_failed`；
- `evidence_item`：`{kind:evidence_kind, result:evidence_result, path:string}`，每层均为封闭对象；
- `evidence_kind`：`pre_state | post_state | ftp_unique | remote_hash | size | mtime`；
- `evidence_result`：`matched | mismatched | unavailable | check_failed`；
- `batch_indeterminate`：`{path:string, error_type:outcome_unknown, message:string, evidence:evidence_item[]}`；
- `download_dir` 的 `skipped` 和 `failed` 数组中的 `path` 均为虚拟远程路径；其 `skipped` 只允许 `symlink_unsupported` 变体；
- `upload_dir` 的三个批量明细数组中的 `path` 和 `evidence_item.path` 均为相对于本次 `local_path` 的规范化相对路径；
- `server_summary`：`{alias:string, description:string|null, protocol:protocol, read_only:boolean, is_default:boolean}`；
- `download_batch_status`：`complete | partial | failed`；
- `upload_batch_status`：`complete | partial | failed | indeterminate`；
- `operation_status`：`completed`。

各工具成功输出的必填字段：

| 工具 | 必填字段 |
| --- | --- |
| `list_servers` | `ok:true`、`servers:server_summary[]` |
| `test_connection` | `ok:true`、`server:string`、`protocol:protocol`、`read_only:boolean` |
| `list_dir` | `ok:true`、`path:string`、`entries:entry[]`、`truncated:boolean` |
| `search_files` | `ok:true`、`path:string`、`matches:match[]`、`truncated:boolean` |
| `get_file_info` | `ok:true`、`path:string`、`type:object_type`、`size:integer|null`、`mtime:mtime` |
| `read_text_preview` | `ok:true`、`path:string`、`content:string`、`encoding:utf-8\|utf-8-sig\|gbk`、`truncated:boolean`、`returned_lines:integer`、`total_lines:integer|null`、`partial_line:boolean` |
| `download_file` | `ok:true`、`remote_path:string`、`local_path:string`、`size:integer`、`mtime:mtime`、`sha256:string` |
| `upload_file` | `ok:true`、`remote_path:string`、`size:integer`、`status:operation_status` |
| `make_dir` | `ok:true`、`path:string`、`created:boolean`、`status:operation_status` |
| `rename` | `ok:true`、`old_path:string`、`new_path:string`、`type:object_type`、`status:operation_status` |
| `move` | `ok:true`、`from_path:string`、`to_path:string`、`type:object_type`、`status:operation_status` |
| `delete` | `ok:true`、`path:string`、`type:object_type`、`status:operation_status` |
| `download_dir` | `ok:true`、`remote_path:string`、`local_dir:string`、`file_count:integer`、`total_size:integer`、`skipped:batch_skipped[]`、`failed:batch_failed[]`、`status:download_batch_status` |
| `upload_dir` | `ok:true`、`remote_path:string`、`file_count:integer`、`total_size:integer`、`skipped:batch_skipped[]`、`failed:batch_failed[]`、`indeterminate:batch_indeterminate[]`、`status:upload_batch_status` |

正式 `outputSchema` 必须把上述共享类型展开为完整 JSON Schema，明确 `required`、类型、枚举、可空字段以及每一层的 `additionalProperties:false`。所有 `outputSchema` 的根节点必须明确声明 `"type":"object"`；需要同时描述成功和错误结构时，在该对象 Schema 内使用 `oneOf`，不得使用只有根级 `oneOf`、没有根级 `type:"object"` 的 Schema。实现期应维护一份内部的旧字段到新字段映射或自动生成的 Schema diff，至少覆盖 `readOnly` → `read_only`、删除统计冗余字段和 `perms`/`hint`、`created` 改为布尔值，以及新增 `status`、`partial_line`、`encoding`、`path`；该材料用于实现与发布检查，不构成面向旧用户的迁移支持。

## 12. 批量处理与资源边界

`upload_dir` 和 `download_dir` 均不设置客户端文件数量上限或批次总字节上限，也不接受 `max_files` 参数。服务不自动拆批，也不阻止 Agent 根据用户任务发起多次独立调用。若未来需要任务级配额、速率限制、并发限制或显式分批，必须另行设计。

`download_file` 和 `download_dir` 不执行客户端文件大小限制。下载仍须遵守第 15 节的完整性检查和本地部分文件清理规则。

`upload_dir` 不为大小限制预先扫描完整本地目录，也不因某个文件超限而整体拒绝。工具按目录遍历顺序逐项处理，并在每个普通文件的实际读取和上传过程中累计字节数：

- `max_file_size_bytes=0` 时不执行上传文件大小限制；
- 上限为正数时，等于上限的文件允许上传；读取到超过上限的第一个字节后立即终止当前文件；
- 超限文件必须上传到远端临时路径，且只有完整传输未超限后才能提交为最终目标；确认删除临时文件且最终目标未被本次单项改变后，将该项写入 `skipped`，`reason_type=size_limit_exceeded`，然后继续处理后续文件；
- 超限跳过项的 `details.configured_limit` 返回配置上限，`details.observed_value` 返回停止时已经观察到的最小字节数，`details.observation=at_least`，`details.remote_committed=false`；不得为取得文件最终大小而继续读取或上传；
- 临时文件清理失败时不得报告为已安全跳过。若能够确定最终目标未改变，则写入 `failed` 并使用 `server_error`；若最终目标状态无法确定，则写入 `indeterminate` 并按第 15 节处理；
- 目录内容在遍历或传输期间可能变化。实际流式计数是大小限制的权威判定，不得只依赖可能过期的本地 `stat` 结果。

批量工具返回的 `file_count` 和 `total_size` 是成功完成项目的统计，不是限制判据；被跳过、失败或结果不确定的项目不计入成功统计。

## 13. 单文件上传限制

`max_file_size_bytes` 对 `upload_file` 和 `upload_dir` 中的每个普通文件表达同一含义：单个上传文件允许的最大字节数。该值为 `0` 时不限制；为正数时边界值等于上限允许上传。它不限制批次文件数量或批次合计大小。

`upload_file` 必须在建立远端连接和创建目标文件前检查本地文件大小。上限为正数且本地文件超过上限时，返回 `size_limit_exceeded` 和第 14 节的 `limit_details`，不得产生远端部分文件。为防止检查后本地文件增长或被替换，实际传输仍须累计读取字节数；若传输期间才发现超限，必须停止并清理本次调用产生的远端临时文件，不得提交最终目标。

覆盖策略仍保持默认拒绝。配置解析必须拒绝负数和 boolean，不得把 `0` 当作缺省值替换为默认上限。

### 13.1 上传临时对象与最终提交

`upload_file` 和 `upload_dir` 的每个文件使用同一提交协议，具体取舍见 [ADR 0007](../../decisions/0007-snapshot-authorized-upload-commit.md)：

- 远端临时对象必须位于最终目标的同一目录，名称格式为 `.<目标文件名>.ft-upload-<16 位小写十六进制>.tmp`；随机部分使用密码学安全随机源生成 64 位随机值。创建前检查名称是否存在，冲突时重新生成，最多尝试 3 次；3 次均冲突时返回 `server_error`。检查通过后不要求协议级原子独占创建，并明确接受检查后被其他写入者占用或替换的残余竞态；不得复用已观察到存在的对象，临时名称不得返回给 Agent；
- 文件内容只写入临时对象。达到 EOF、未超过上传上限、远端写句柄成功关闭且必要的大小检查通过后，才允许把临时对象提交到最终目标；不得先删除最终目标；
- `overwrite=false` 时，只在每个文件开始上传前检查一次最终目标。该检查是本次调用的授权快照：当时已存在即返回 `policy_rejected`；当时不存在即允许本次调用在完整写入临时对象后执行普通 rename，不在提交前进行第二次存在性检查，也不要求服务器提供原子 no-replace。首次检查后由其他来源创建或替换同名目标，不视为本次调用违反 `overwrite=false`；若服务器明确因目标冲突拒绝 rename，保持其拒绝结果，不得删除或强制替换，能够确定为目标冲突时返回 `policy_rejected`，否则返回 `server_error`；
- `overwrite=true` 仅在 driver 能确认服务器支持不会先删除旧目标的原子替换时允许提交。能力未知或不支持时，在保持旧目标不变的前提下返回 `policy_rejected`，不得降级为“删除旧目标后 rename”；
- 提交命令得到明确成功响应后才报告成功。提交请求发出后连接中断或响应丢失时禁止重放，按第 15 节返回 `outcome_unknown`；最终路径存在、名称或大小相同都不足以单独证明成功；
- 提交前失败、取消或超限时必须清理临时对象。能够确认最终目标未改变但临时对象清理失败时返回 `server_error` 并说明可能存在远端临时残留；最终目标或提交状态无法确认时返回 `outcome_unknown`；
- 实现必须能够识别本产品的临时命名空间，用于测试和经授权的清理，但不得自动删除无法确认归属于本次调用的对象。

## 14. 错误契约

进入工具运行时后的参数范围、业务规则拒绝、远端失败和配置错误均作为工具执行错误返回 `isError=true`。调用前被 FastMCP / JSON Schema 拒绝的请求属于框架参数错误，遵循第 10 节的分层规则。

统一结构化错误的公共字段为：

- `ok:false`；
- 稳定 `error_type`；
- 净化后的 `message`；
- `retryable:false`；
- 可选安全 `hint`；
- 仅特定错误允许出现的受控 `details`。

`error_type` 的封闭枚举为：

`invalid_config | credential_missing | invalid_argument | not_found | invalid_path | symlink_unsupported | policy_rejected | size_limit_exceeded | permission_denied | connection_unavailable | integrity_check_failed | server_error | outcome_unknown`。

统一错误对象按 `error_type` 构成封闭的 discriminated union：

- `invalid_config`、`credential_missing`、`invalid_argument`、`not_found`、`invalid_path`、`symlink_unsupported`、`policy_rejected`、`permission_denied`、`connection_unavailable`、`integrity_check_failed`、`server_error`：只允许公共字段和可选 `hint`，不得包含 `details`；
- `size_limit_exceeded`：必须包含字段 `details:limit_details`；
- `outcome_unknown`：必须包含字段 `details:outcome_unknown_details`。

`limit_details` 与第 11.7 节的 `upload_limit_details` 是同一个封闭对象：

```text
{
  limit_kind: upload_file_bytes,
  configured_limit: integer >= 1,
  observed_value: integer > configured_limit,
  observation: exact | at_least,
  remote_committed: false
}
```

`upload_file` 在远端写入前根据稳定本地大小拒绝时使用 `observation:exact`；若预检后文件增长并在流式传输中才发现超限，则使用 `observation:at_least`。两种情况都必须保证最终远端目标未由本次调用提交，因此固定为 `remote_committed:false`。`upload_dir` 的逐项流式超限属于可继续执行的批量跳过项，使用同一 `upload_limit_details`，不返回工具级 `size_limit_exceeded`。

`outcome_unknown_details` 为封闭对象，所有字段必填：

```text
{
  operation: upload_file | upload_dir | make_dir | rename | move | delete,
  phase: request_dispatched | remote_execution | response_wait | postcondition_check,
  paths: string[1..],
  evidence: evidence_item[]
}
```

其中 `paths` 只包含相关虚拟远程路径；`evidence_item` 使用第 11.7 节的封闭结构。`outcome_unknown` 固定为 `retryable:false`。所有错误的 `message`、`hint`、`details` 和 evidence 均不得包含底层异常文本、真实服务器路径、连接信息或凭据信息。未来若需要为其他错误增加 `details`，必须先修改本 Spec 和正式 Schema，不得以 `additionalProperties:true` 扩展。

每个工具的 `outputSchema` 以根级 `type:"object"` 和内部 `oneOf` 描述成功对象与统一错误对象。MCP Client 会校验 `isError=false` 的成功结构；FastMCP 4.0.2 / MCP Client 不会强制校验 `isError=true` 的结构化错误。因此错误分支仍是公开契约，但必须由项目自己的服务端单元测试和 MCP 线级契约测试保证。框架参数错误的 `structuredContent` 为 `null`，不参与工具 `outputSchema` 校验。

未知工具和无法解析的请求继续使用 JSON-RPC 协议错误。

SFTP 能确定对象不存在时统一映射为现有 `not_found`，不得映射为 `connection_unavailable`。FTP 无法区分不存在和无权限时允许返回 `permission_denied`，但消息不得声称已确定具体原因。

`invalid_argument` 用于已经进入工具运行时、但字段值违反与路径语义无关的业务参数规则；本轮用于空 `pattern` 或包含路径分隔符的 `pattern`。远程路径本身非法仍返回 `invalid_path`。

`symlink_unsupported` 固定为 `retryable:false`。消息只说明请求路径包含不受支持的符号链接，不得包含或推测链接目标；调用方应改用目标对象在配置 root 内的正常虚拟路径，若不存在这样的路径则不应访问该对象。

`integrity_check_failed` 固定为 `retryable:false`，用于下载已经正常结束但已知远端大小与实际落盘大小不一致，或者能够证明远端文件在传输期间发生变化的情况。消息必须说明下载结果未通过完整性检查；能够确定来源变化时可以说明这一事实，但不得暴露真实路径、底层异常或未经验证的原因。

凭据和连接错误不得向 Agent 返回 host、端口、用户名、环境变量名、key path、指纹或凭据来源。详细诊断进入 doctor 或受保护日志。

内部自动重试结束后，对外所有失败均为 `retryable=false`。`server_error.retryable` 从 `true` 调整为 `false`。

## 15. 重试与结果不确定

禁止对写操作进行盲目完整重放。

发生连接异常时：

1. 判断异常是否发生在远端业务操作开始前；
2. 若能确定尚未开始，可重新建立连接并执行一次；
3. 若可能已经执行，只能按下表规定重新连接并核验远端状态；
4. 只有证据达到下表的成功判据时，才将操作视为已经完成；
5. 只有下表明确允许，且证据证明远端操作未发生时，才允许执行一次；
6. 状态检查失败或无法可靠判断时，返回 `outcome_unknown` 并要求人工核验。

各工具恢复判据：

| 工具 | 操作前快照 | 成功证据 | 连接异常后是否允许重放 |
| --- | --- | --- | --- |
| `make_dir` | 目标是否存在及对象类型 | 目标为目录 | 目标明确不存在时允许一次；类型冲突或无法检查时返回 `outcome_unknown` |
| `upload_file` | 目标是否存在、覆盖策略、本地大小及可用内容标识 | 远端提供并匹配可靠内容哈希；只有大小相等属于弱证据，不能证明成功 | 远端写入开始后禁止自动重放；证据不足返回 `outcome_unknown` |
| `upload_dir` | 每个目标的存在状态、覆盖策略、本地大小及可用内容标识 | 按单文件分别判断 | 仅对可证明尚未开始的单项允许一次；任一单项不确定时记录 `outcome_unknown`，批量状态为 `indeterminate` |
| `rename` | 源与目标的存在状态、类型及可获得的身份信息 | 身份证据证明原源对象位于目标且源已不存在 | 请求发出后发生连接异常时默认禁止重放；仅凭“源不存在、目标存在”不足以证明成功 |
| `move` | 源与目标的存在状态、类型及可获得的身份信息 | 身份证据证明原源对象位于目标且源已不存在 | 请求发出后发生连接异常时默认禁止重放；目标可能被替换时返回 `outcome_unknown` |
| `delete` | 目标的存在状态、类型及可获得的身份信息 | 只有本次请求取得明确成功响应，或未来存在可关联本次请求的服务端事务/审计回执时才可确认 | 请求发出后发生连接异常或响应丢失时一律返回 `outcome_unknown`，不得重放；仅凭目标不存在不能证明由本调用删除 |

FTP/SFTP 不能提供可靠对象身份或远端内容哈希时，不得以文件名、存在性或大小相同替代强证据。第 12、13 节要求的临时路径只用于避免超限或失败传输暴露为最终目标，不能作为响应丢失后的身份或成功证据，也不改变本节的 `outcome_unknown` 判定。

能力边界明确如下：只有 FTP 服务端为相关对象提供 RFC 3659 `unique` fact 时，才可把该值作为 rename 或 move 的身份核验证据；SFTP v3 常规属性以及没有 `unique` fact 的 FTP 不提供本轮认可的稳定对象身份。FTP `unique` 可以识别 delete 操作前对象或发现路径仍存在、已被替换，但“操作前 unique + 操作后路径不存在”不能建立本次请求导致删除的因果关系。写请求已经发出后发生连接异常时，rename、move 和 delete 按上述判据返回 `outcome_unknown`，不得重放。upload 只有在服务端提供并匹配可靠远端内容哈希时才能在响应丢失后确认成功；否则在写入开始后的连接异常中返回 `outcome_unknown`。

下载不是远端写操作，不使用 `outcome_unknown`。`download_file` 失败、取消或连接异常时删除本次调用产生的部分文件，不得把部分文件作为成功结果；连接异常返回工具级 `connection_unavailable`。`download_dir` 的单项连接异常在清理该项部分文件后写入 `failed`，其 `error_type=connection_unavailable`，并按已完成项数量返回 `partial` 或 `failed`；整批无法开始时返回工具级 `connection_unavailable`。若部分文件清理本身失败，则返回 `server_error` 并使用净化消息说明可能存在本地残留，不使用 `outcome_unknown`。

远端大小已知时，下载正常完成后落盘大小必须一致；不一致时，`download_file` 返回工具级 `integrity_check_failed`，`download_dir` 将该项写入 `failed` 且 `error_type=integrity_check_failed`，并清理本次调用产生的无效落盘文件。能够证明传输期间远端文件发生变化时执行相同处理。远端大小未知但传输正常到达 EOF 时，可以成功返回实际落盘大小；发生连接异常时仍按上一段返回 `connection_unavailable` 或批量失败项。本轮不引入远端哈希、版本快照或未知大小文件的完整流式限制方案。

`idempotentHint=true` 不代表服务必须自动重试；annotation 描述重复调用的状态效果，内部重试仍必须遵守上述结果核验规则。

## 16. 契约生效与不兼容策略

本轮以尚无需要兼容的既有用户为前提，新的配置和 MCP 契约直接作为后续用户的初始契约，不为旧版配置或调用方提供迁移兼容层。

相对于当前开发基线，以下不兼容变化必须在实现、测试和当前文档中一次性完成：

- 增加 `list_servers` 和服务器 `description`；
- 配置格式版本调整为 `version:2`，其他版本不再接受；
- root 改为必填；
- `readOnly` 默认改为 `true`；
- SFTP 主机密钥信任决定移到用户认证之前，可能首次写入 TOFU 状态的工具设置 `readOnlyHint=false`；
- 真实服务器路径改为虚拟路径；
- 多个成功输出字段删除或重命名；
- 删除客户端批次文件数和总字节限制；`max_file_size_bytes` 改为仅限制每个上传文件，并允许 `0` 表示不限制；
- 业务失败改为 `isError=true`；
- `server_error.retryable` 从 `true` 改为 `false`；
- SFTP 不存在对象调整为 `not_found`；
- 新增运行时参数错误 `invalid_argument` 和下载完整性错误 `integrity_check_failed`；
- 批量结果增加明确完成状态。

文档只描述新契约的正确配置和使用方式，包括虚拟路径示例、必填 root、`readOnly:true` 默认值、显式启用写能力以及服务器 description 的用途；不编写旧版本迁移步骤或回滚承诺。

本轮不提供配置回滚兼容。开发实现失败时可以把代码、Schema、测试和文档整体回退到[执行清单](../../development/plans/next-development.md)记录的 Start SHA，但这不代表 v2 配置能够供旧代码读取；任何配置替换都必须由用户显式执行，setup 不得自动覆盖现有非 v2 配置。

Git 回退不撤销已经发生的外部状态。开发和 live 测试前必须按执行清单记录配置及 known-hosts 的备份与权限、staging 目录、远端测试目录和上传临时命名空间；回退时只清理由本轮测试明确创建且归属可证明的 staging 或远端临时对象，对 `outcome_unknown` 项逐项人工核验。已完成或归属不明的远端写入不得自动删除，必须明确记录为代码回退范围之外的不可逆外部状态。

## 17. 验收标准

- 第 11.7 节列出的全部 14 个工具均具有准确 title、description、字段说明、annotations 和精确 Schema；测试从运行时 `tools/list` 比较完整工具名集合而不是只断言数量。title 和 description 非空、不含禁止连接或凭据信息，并由正式 Schema 快照完整比较；成功与统一错误结构的每层对象均明确 `required`、类型、枚举、可空性和 `additionalProperties:false`。
- setup 在无现有配置时生成 `version:2` 配置；遇到其他配置版本时明确拒绝，不自动迁移或覆盖，并给出备份、显式删除或替换后重新运行 setup 的提示。
- 默认配置路径下文件不存在时 `list_servers` 返回空列表；`FT_FTP_MCP_CONFIG` 显式路径不存在，以及配置不可读、损坏、版本错误、`servers` 为空或非法时返回 `invalid_config`。
- `list_servers` 不连接服务器、不读取凭据、不返回禁止字段；`description` 的疑似敏感内容由 doctor 告警但不硬拒绝。
- 模糊服务器选择可以通过 alias 和 description 完成，未知 alias 不泄露服务器清单。
- `test_connection` 不再暴露连接、账号、root 和凭据来源。
- Agent 输入输出中的所有远程路径均为虚拟远程路径，driver 返回值和异常在业务边界完成反向映射或净化；规范明确允许的本机路径字段保持本机路径语义。
- 敏感信息测试只扫描服务生成的连接元数据、诊断消息、异常映射、错误对象的 `message`/`hint`/`details`、批量 `message` 和禁止出现的结构化字段；至少注入并覆盖 host、port、username、真实 root、key path、fingerprint、凭据来源和不应枚举的 alias，并包含底层异常携带真实 root 的场景。
- denylist 不扫描或禁止远端文件原文、`read_text_preview.content`、用户提供的文本、文件名、虚拟路径，以及契约明确允许的 alias 和 description；这些字段仍须遵守各自的路径边界和 description doctor 告警规则。
- root 边界前缀、`.`、`..`、反斜杠、NUL、虚拟 `/` 和真实路径误传均有测试。
- 服务器目录项名称按不可信输入处理；覆盖空名称、`.`、`..`、NUL、分隔符、绝对路径、盘符、UNC、Windows 保留名称和嵌套逃逸，验证远程 child 与本地目标均不能逃出各自边界，且非法下载项稳定返回 `invalid_path`。
- 虚拟根不能被删除、移动或重命名。
- SFTP 配置 root 本身或其可见路径段为符号链接时返回 `invalid_config`；所有单对象工具覆盖中间路径段、最终对象、断裂链接及检查失败场景，检测到链接时不调用 `readlink`、不解析目标并返回 `symlink_unsupported`。强制 `lstat` 无法可靠完成时必须 fail-closed，不得降级执行原操作。
- `list_dir` 可以将普通目录中的链接条目显示为 `type:symlink`，但不返回目标路径或目标属性；以链接作为待列目录时拒绝。`search_files` 不进入或返回链接；`download_dir` 和 `upload_dir` 以 `reason_type=symlink_unsupported` 逐项跳过并继续，批量根路径为链接时工具级拒绝。
- FTP 在服务器或驱动明确报告链接时执行相同拒绝或跳过；测试和文档不得把 FTP 的启发式识别描述为可靠保证。服务器配置的虚拟目录映射按普通目录处理；FTPS 不在协议或验收范围内。
- 本地上传覆盖根链接、中间目录链接、文件链接、断裂链接、Windows junction/reparse point 和检查后替换；检测到链接时不读取内容，打开后对象身份无法与打开前检查一致时 fail-closed。
- 默认配置为只读，写操作在连接前拒绝。
- SFTP 配置指纹或已保存 TOFU 主机密钥在用户认证前完成比较；不匹配时不发送认证材料。配置指纹验证成功和首次 TOFU 均以 alias 为键原子持久化到独立 known-hosts，且不会写回配置文件。覆盖多进程竞争、原子写中断、损坏或重复记录、锁失败、权限失败和显式配置指纹模式。
- 除 `list_servers` 外，所有可能首次建立 SFTP 连接并写入 TOFU 状态的工具均为 `readOnlyHint=false`；读取工具的描述明确该副作用。
- `max_file_size_bytes` 接受非负整数，`0` 表示不限制；负数和 boolean 被配置校验拒绝。
- `upload_file` 的上传文件上限在 FTP/SFTP 下均生效，边界值允许，超限不产生最终远端文件；检查后文件增长也受实际传输计数约束。
- `upload_dir` 不预扫描完整目录；逐文件执行同一上传大小限制，超限项安全清理临时文件后记入 `skipped` 并继续后续文件。覆盖已知超限、传输中增长、全部超限、部分超限、临时文件清理失败及 `max_file_size_bytes=0` 场景。
- 上传临时对象使用同目录 64 位随机名称，初始冲突最多重试 3 次，且只在完整写入后提交；`overwrite=false` 只以传输前首次目标检查作为授权快照，不要求原子独占临时创建或原子 no-replace 提交；`overwrite=true` 不先删除旧目标，只在确认服务器支持安全原子替换时允许。覆盖提交能力不足、首次检查时目标已存在、检查后并发创建或替换、临时名称冲突或检查后被占用、写入/关闭/rename 失败、rename 响应丢失及清理失败均有 FTP/SFTP 测试。
- 上传和下载均无客户端文件数量或批次总字节限制；下载不受单文件大小限制。`file_count` 和 `total_size` 仅统计成功项。
- `max_bytes` 超限明确拒绝；预览覆盖 BOM、三种编码、完整字符边界、超长首行、首字符大于预算、`returned_lines`、`total_lines` 和 `partial_line` 的组合语义。
- FTP `MLSD`/`MDTM` 与 SFTP 合法时间输出带 `Z` 的 ISO 8601 UTC；FTP `LIST` 及其他无法可靠确定的时间返回 `null`。
- `download_dir` 能区分 `complete`、`partial` 和 `failed`，不返回 `indeterminate` 数组或 `status:indeterminate`；`upload_dir` 能区分 `complete`、`partial`、`failed` 和 `indeterminate`，并返回必填的 `indeterminate` 数组。测试覆盖合法空目录、全部跳过、部分失败、全部失败和上传单项结果不确定；下载明细使用虚拟远程路径，上传明细使用相对于本次 `local_path` 的规范化相对路径。
- `batch_skipped.reason_type`、`batch_failed.error_type`、`batch_indeterminate.error_type` 和 evidence 均符合第 11.7 节的封闭枚举；不确定项可以逐项定位，不要求或建议调用方整体重跑。
- 合法成功结果符合 `outputSchema` 的成功分支；故意缺少成功必填字段时，MCP Client 必须拒绝该结果。
- 运行时业务失败返回 `isError=true`，并包含符合项目错误契约的 `structuredContent`；内部重试结束后 `retryable=false`。
- 项目测试必须主动校验所有结构化错误对象，因为 FastMCP 4.0.2 / MCP Client 不会替服务端校验 `isError=true` 的输出。
- 缺少必填字段、字段类型错误、未知字段和固定枚举错误返回 `isError=true`、`structuredContent=null` 的框架工具错误。
- `max_bytes` 越界和 `confirm != true` 能够进入工具函数并返回对应统一结构化错误；空 pattern 和包含路径分隔符的 pattern 返回 `invalid_argument`；`upload_file` 实际对象超过正数上传上限时返回 `size_limit_exceeded + limit_details`。
- 统一错误的 `error_type`、`details` 变体和所有嵌套对象符合第 14 节的 discriminated union；未获允许的错误不得返回 `details`。
- 根节点只有 `oneOf` 的 `outputSchema` 作为反例测试；正式 Schema 必须同时包含根级 `type:"object"`。
- 每次调整 FastMCP 或 MCP SDK 版本时，重新运行最小参数与输出契约测试。
- Codex 和 WorkBuddy 均通过真实宿主冒烟测试，并能接受包含 annotations 的工具清单后继续正常调用；服务端 annotations 由正式 Schema、MCP Client 和能力探针完整验证，且至少一个真实宿主完成模型侧端到端验证。在两个宿主中，`isError=true` 时 Agent 均能取得稳定 `error_type` 和契约要求的结构化详情；对 `upload_dir` 的 `isError=false`、`ok=true`、`status=indeterminate`，Agent 均能识别不确定项、向用户告警且不整体重跑。宿主是否消费、展示或向模型透传 annotations 不属于项目保证；任一宿主不满足前述强制端到端错误与不确定结果条件时仍阻塞交付并退回 Spec。
- SFTP 不存在对象返回 `not_found` 且不触发连接类自动重试。
- 使用可注入故障的 fake driver，对上传、批量上传、创建目录、重命名、移动和删除分别覆盖“请求前断线”“服务端可能已完成但成功响应丢失”“核验失败”，以及并发重建、目标替换和批量上传中途断线场景；明确覆盖 SFTP、无 FTP `unique` fact 和具有 FTP `unique` fact 三类身份核验能力。
- 写操作不盲目重放，状态无法确认时返回 `outcome_unknown`。
- 下载失败、取消或连接异常不遗留本次调用产生的部分文件；`download_file` 连接异常返回工具级 `connection_unavailable`，`download_dir` 单项连接异常进入 `failed`，下载不使用 `outcome_unknown`。远端大小已知时必须验证落盘大小，不一致或能够证明来源在传输期间变化时返回 `integrity_check_failed`；远端大小未知但传输正常到达 EOF 时允许成功并返回实际落盘大小。
- `docs/schema/mcp-tools.json` 可由 `scripts/export_mcp_schema.py` 重建且无差异。
- 项目治理入口和 Schema 测试不再把历史 Schema 草案作为当前事实来源。
- pytest、ruff、mypy、Schema 契约测试及授权范围内的 FTP/SFTP live 测试通过。

## 18. 审查要求

本轮改变路径隔离、只读默认值、公开 MCP 契约、错误语义和危险操作恢复策略，属于高影响变更。

实现前必须进行独立设计审查，重点检查：

- 虚拟路径到真实路径的映射；
- root、`/` 和边界前缀处理；
- 符号链接拒绝策略、SFTP 逐段检查、FTP 检测能力边界及本地上传链接/reparse point 检查；
- annotations 的准确性；
- annotations 的服务端保证、真实宿主端到端证据和第三方宿主处理边界；
- 输入输出信息最小化；
- 写操作结果核验和恢复语义；
- 新契约一致性及实现失败时将代码、Schema、测试和文档整体回退到[执行清单](../../development/plans/next-development.md)记录的 Start SHA 的路径；不得把该代码回退描述为配置 v2 到 v1 的迁移或兼容回滚。

实现完成后必须基于固定 Candidate SHA 进行独立代码审查。P0/P1 问题解决或由用户明确接受后，方可合并或发布。

## 19. 已知残余风险

本轮完成后仍存在：

- WorkBuddy 模型侧当前看不到四种 MCP annotations，可能依据工具描述作出不完整或错误的风险推断；本项目已验证服务端正确发送、Codex 模型侧可以取得、WorkBuddy 能接受同一工具清单并正常调用，但尚未通过原始入站报文确定 WorkBuddy 内部的具体丢失层级。WorkBuddy 的工具允许列表、审批设置和服务端强制规则仍是实际安全控制；
- 本地上传路径没有允许根目录白名单。可利用链为：远端文件或文本包含恶意指令，诱导 Agent 读取进程有权访问的本机文件，再通过 `upload_file` 或 `upload_dir` 外传；本轮只披露并保留该风险，不实现白名单，也不承诺其下一轮优先级；
- FTP 无法可靠提供 canonical path 和符号链接语义，底层链接可能被服务器作为普通目录暴露；
- SFTP 逐段 `lstat` 与实际业务操作之间仍存在 TOCTOU，攻击者或并发进程可能在检查后替换路径对象；
- 本地上传的逐段检查、打开前检查和句柄复核能够缩小但不能消除目录项或父目录被并发替换的 TOCTOU；可靠边界仍依赖本机账号权限和受信任的本地文件系统；
- `overwrite=false` 采用传输前单一检查点的授权快照，而不是持续到提交时的并发无覆盖保证；检查通过后，其他来源可能创建或替换最终目标，普通 rename 可能覆盖该对象，也可能被服务器拒绝。远端临时名称同样只有创建前检查，没有协议级原子独占保证；极低概率的检查后同名占用可能导致临时对象冲突或覆盖。项目负责人已明确接受这些兼容性优先的并发风险；
- `confirm=true` 不能证明人工确认；
- 远端文本和文件内容可能包含恶意指令；
- staging 没有 TTL、配额和自动清理；
- 缺少全局频率和并发限制；
- 缺少服务端总执行超时和取消协作机制；
- 上传和下载均不限制单次批量调用的文件数量或合计字节，下载也不限制单文件大小；超大目录、超长传输、磁盘耗尽、远端配额耗尽和大量小文件带来的资源风险由本决策明确接受，服务端限制仍可能独立拒绝操作；
- `BUG-003` 所述 FTP `NLST` 未知大小绕过批量下载总字节预检的问题，因本轮取消全部客户端下载大小与批次总量限制而不再适用；这不代表未知大小下载的资源风险已经消失；
- 远端大小未知且传输正常到达 EOF 时只能确认传输流程正常结束，不能证明取得了远端文件某一时刻的一致快照；即使下载前后大小相同，也无法排除等长替换或无法观察到的并发内容变化。本轮不要求服务器提供内容哈希或版本快照；
- FTP 服务器可能违反 RFC 3659，将本地时间伪装成语法合法的 `MLSD modify` 或 `MDTM` UTC 值；客户端无法仅凭响应自证其时区真实性，会按协议语义输出；
- `BUG-007` 和 `INV-001` 尚未在本轮解决。

这些风险不得在发布说明中描述为已经解决。
