# FT Agent FTP 插件：MCP 工具 Schema 草案 v0.3

## 产品裁定（实现必须遵守）

- `upload_file` 和 `upload_dir`：默认拒绝覆盖；用户明确确认后，显式传入 `overwrite=true` 才允许覆盖。
- `rename` 和 `move`：目标已存在时统一拒绝覆盖，返回 `policy_rejected`。
- `make_dir`：幂等操作；重复创建已经存在的目录仍返回成功，`created` 为空列表。也就是说，同一个请求执行一次或多次，最终结果和成功状态一致，不会因为目录已存在而报错。
- `server_error`：允许工具内部自动重试一次；第二次仍失败后返回结构化错误，并禁止继续自动重试。

> 依据：《FT Agent FTP 插件（MVP）产品需求文档_v0.8.md》第四章（工具清单）、5.3（⑦路径定位/⑧传输异常/⑨覆盖门控/⑩文本预览）、第六章安全设计、附录 D 已知坑。
> 性质：参数级实现草案，"描述即文档"的定稿候选——description 均为中文，联调期按真实调用失败案例持续打磨（PRD 4.2 原则 4）。
> 标注：每工具标注批次（PoC 7 个 / MVP 新增 6 个）。Schema 用 JSON Schema（draft-07 保守子集）表达。

## 评审修订说明（v0.1 → v0.2）

本次为独立评审修订，主要改动：

1. **路径边界补强（最高优先级）**：v0.1 只写了"绝对路径"，未告诉模型用户给相对路径 / Windows 盘符路径（`C:\…`、`报表/昨日订单.csv`）时该怎么办。v0.2 在"通用约定"与各路径参数 description 中明确：服务器路径必须是 Unix 风格、以 `/` 开头；相对/盘符路径不得透传，应先 `search_files`/`list_dir` 定位出绝对路径，工具收到非法路径返回 `invalid_path` 并给出修正指引。
2. **`server` 参数落入每个 schema**：v0.1 声明"所有工具均带 server 但 schema 中不再重复列出"——模型只看得到 schema，看不到本文档，等于该参数不可发现。v0.2 将 `server` 显式写入全部 13 个工具的 properties。
3. **删除 `enum:[true]` 方言隐患**：`delete.confirm` 由 `"enum": [true]` 降级为 `type: boolean` + 逻辑层校验，避免部分客户端 schema 校验首次调用即失败（PRD 附录 D 已知坑 1）；拒绝信息含可执行的修正指引。
4. **错误 envelope 增加重试语义**：补充 `retryable` 字段定义（"同参数原样重发是否可能成功"）与逐 `error_type` 行为表，并新增全局规则"同一调用最多修正一次，禁止同参连发"，防模型循环重试烧 token；`policy_rejected` 的 hint 明确"修正参数重调 ≠ 重试"。
5. **description 全面重写**：每个工具补齐"何时用 / 何时不用 / 与相邻工具的区别"，重点消除三组混淆——`rename` vs `move`、`download_file` vs `download_dir`、`list_dir` vs `search_files`。
6. **PRD 一致性修正**：`list_dir` 条目与 `get_file_info` 返回补 `perms` 字段（PRD 4.1 返回要点含"权限"，v0.1 遗漏）；`download_dir.max_files` 明确只能调低、不能调高突破护栏。
7. **产品裁定回写**：`upload_file`/`upload_dir` 默认拒绝覆盖，显式 `overwrite=true` 且取得用户确认后允许覆盖；`rename`/`move` 拒绝覆盖已存在目标；`make_dir` 目录已存在视为成功；`server_error` 允许内部自动重试一次。
8. **Schema 方言白名单**：明确允许与禁止的关键字清单（见 3.1），实现与后续加工具时有章可循。

### v0.3 开发前契约收口（2026-09-10）

- `download_dir.remote_path` 明确为必填。
- 文本内容编码固定为 BOM → UTF-8 严格解码 → GBK 回退；截断时 `total_lines=null`。
- 批量上传与下载保留空目录、跳过软链接，并以开始时的目录枚举快照执行。
- 批量双上限固定为服务器级 `max_batch_total_bytes`（默认 10GB）和 `max_batch_files`（默认 500）；单文件仍受 `max_file_size_bytes` 限制。
- FastMCP/Pydantic 生成的 `anyOf` 与 `additionalProperties` 纳入兼容方言，实际兼容性由 MVP 客户端矩阵验证。

---

## 0. 通用约定

### 0.1 路径规范（模型必读，已写入各工具 description）

| 路径类型 | 规范 |
| --- | --- |
| 服务器端路径（`path` / `remote_path` / `from_path` / `to_path`） | **Unix 风格绝对路径，以 `/` 开头**，如 `/reports/2026-09/昨日订单.csv`。即使本机是 Windows，服务器路径也不用盘符、不用反斜杠。相对路径（`reports/x.csv`）、盘符路径（`C:\reports`）、任意位置含完整 `..` 段的路径均不合法，直接透传会返回 `invalid_path`；`.` 段会静默规范化 |
| 本机路径（`local_path`） | 本地操作系统风格**绝对路径**，Windows 可写 `D:/data/report.csv` 或 `D:\data\report.csv` |

**模糊路径处理流程（写入 search_files / download_file / upload_file 的 description）**：用户说不清确切路径/文件名（"上周那个对账文件"）时，模型必须先用 `search_files` 或 `list_dir` 收敛候选，把候选展示给用户确认后再执行下载/上传/删除等操作，**禁止凭猜测拼接路径直接调用**——防 550 错误与写错位置（PRD 5.3 ⑦）。

### 0.2 `server` 参数（所有工具均含，required 恒不含它）

```json
"server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
```

**实现约定**：注册到 MCP 客户端时，上述 `server` 定义必须并入每个工具的 properties。为免歧义，本文档各工具 schema 中已显式写出。

### 0.3 统一错误返回（所有工具）

```json
{
  "ok": false,
  "error_type": "permission_denied | not_found | connection_unavailable | credential_missing | policy_rejected | invalid_path | size_limit_exceeded | server_error",
  "message": "该账号无权写入 /reports/xxx，或路径不存在（FTP 550）",
  "retryable": false,
  "hint": "请检查账号权限或确认路径是否正确；也可用 search_files 或 list_dir 定位正确路径"
}
```

**`retryable` 的精确定义**：**同参数原样重发该调用，是否有可能成功**。它不约束"修正参数后重新调用"——那属于新的正确调用，不是重试。

**逐类型行为表**（供实现生成 hint 时对齐，也是模型的预期行为约定）：

| error_type | retryable | 模型应当怎么做 |
| --- | --- | --- |
| `permission_denied` | false | 停止重试；向用户转述无权限；不要换着花样反复尝试同一目录 |
| `not_found` | false | 用 `search_files` / `list_dir` 定位正确路径后再调用（换正确参数，不是重试） |
| `connection_unavailable` | false | 工具内部已自动重试 1 次仍失败；**停止调用**，提示用户检查网络/服务器状态 |
| `credential_missing` | false | 提示用户在 MCP 会话外运行 `cred` / `setup` 配置凭据，完成后重试 |
| `policy_rejected` | false | 按 hint 修正调用方式（如先取得用户确认再显式传 `confirm: true`）；不得原样重发 |
| `invalid_path` | false | 把路径改为以 `/` 开头的服务器绝对路径；相对/盘符路径先用 `search_files` / `list_dir` 定位 |
| `size_limit_exceeded` | false | 缩小范围（更小的子目录 / 更小的 `max_bytes` / 更少的文件）；不得调大参数绕过上限 |
| `server_error` | true | 允许重试 **1 次**；仍失败则停止并报告用户（评审补充：PRD 5.3 ⑧ 未细分此类型，属扩充） |

**防循环重试全局规则**（写进错误 hint 的措辞基调）：收到 `ok: false` 且 `retryable: false` 时，模型最多做**一次**参数修正后再次调用；若再次失败，必须停止并报告用户，禁止第三次调用。

- `message` 面向 Agent 与用户转述，中文、语义化（PRD 5.3 ⑤）；权限与"不存在"无法区分的服务器按模糊提示处理，不猜（PRD 5.3 ⑤）
- 成功返回统一带 `"ok": true` + 各工具定义的业务字段

### 0.4 工具选用速查（维护者对照用，非模型可见）

| 意图 | 用哪个 | 不用哪个 |
| --- | --- | --- |
| 看某目录下一层 | `list_dir` | 不是 `search_files`（那是跨层递归） |
| 按"上周的对账文件"找路径 | `search_files` | 不要直接猜路径调 download/upload |
| 下载单个文件 | `download_file` | 目标是目录时用 `download_dir` |
| 看文本/CSV 表头 | `read_text_preview` | 要全文件统计时用 `download_file` |
| 同目录改名 | `rename` | 跨目录挪位置用 `move` |
| 传单个文件 | `upload_file` | 传整个目录用 `upload_dir` |

### 0.5 返回控量约定（PRD 4.2 原则 5）

- `list_dir` 条目上限 500；`search_files` 结果上限 50；两者截断时返回 `truncated: true`，并在返回 `hint` 中建议缩小范围的手段
- 批量工具（`download_dir` / `upload_dir`）返回汇总统计与失败清单，**不逐文件罗列**
- 文件内容一律不进上下文：文本走 `read_text_preview`（有字节上限），其余走 `download_file` 落盘后由 Agent 本地能力读取

---

## 1. PoC 工具（7 个）

### 1.1 `test_connection`

description：`测试与指定 FTP/SFTP 服务器的连接是否可用：验证地址可达、凭据有效，并返回服务器信息与当前账号的访问范围（root 监禁目录、只读状态、凭据来源）。适用场景：首次配置后确认连通性；或其他工具返回 connection_unavailable / credential_missing 错误后用于排查。本工具不做任何文件操作。可选参数 server 指定目标服务器别名，缺省使用默认服务器。`

```json
{
  "type": "object",
  "properties": {
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": []
}
```

返回：`{ ok, server(别名), protocol, host, banner(服务器欢迎信息摘要), username, root(监禁根,未配置为 null), readOnly, credential_source(keyring|env) }`

### 1.2 `list_dir`

description：`列出服务器上指定目录的下一层内容（名称、类型、大小、修改时间、权限），不递归子目录。path 必须是以 / 开头的服务器绝对路径；用户只给了相对路径或模糊描述（如"报表目录"）时，先用本工具从根目录 / 或已知上层目录逐级浏览定位，不要把相对路径直接传入。条目超过 500 条时截断并返回 truncated=true，此时建议改用 search_files 按名称模式缩小范围。本工具只看目录结构，不返回文件内容；查看文本文件开头请用 read_text_preview（MVP），下载文件请用 download_file。`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "目录的服务器绝对路径，以 / 开头，如 /reports/2026-09。相对路径、盘符路径（C:\\…）不合法" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["path"]
}
```

返回：`{ ok, path, entries: [{ name, type(file|dir), size, mtime, perms }], total_count, returned_count, truncated, hint }`
门控：条目上限 500（PRD 4.2 原则 5 返回控量）；截断时 `hint` 建议 search_files 或列更具体的子目录。

### 1.3 `search_files`

description：`按名称模式在服务器上递归查找文件/目录，跨越多层子目录，匹配名称而非内容。当用户的目标路径或文件名不确定（如"上周的对账文件"）时，必须先用本工具或 list_dir 收敛候选，把候选清单展示给用户确认后再执行下载/上传等后续操作，禁止凭猜测拼接路径直接操作。pattern 支持 *（任意字符串）与 ?（单个字符），如 *订单*、*.csv、report_2026??.xlsx。搜索范围限定在服务器 root 内，递归深度默认 5 层，结果最多返回 50 条并附 truncated 标记。只需查看某一目录的下一层时，用 list_dir 更快。`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "搜索起始目录的服务器绝对路径，以 / 开头；不确定时从 / 开始" },
    "pattern": { "type": "string", "description": "通配符模式，* 匹配任意字符串、? 匹配单个字符，如 *对账*、*.csv" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["path", "pattern"]
}
```

返回：`{ ok, matches: [{ path, type, size, mtime }], total_matches, returned_count, truncated }`
门控：仅在 jail 内搜索；递归深度上限（默认 5 层）；结果上限 50 条（PRD 4.1）。

### 1.4 `get_file_info`

description：`获取服务器上单个文件或目录的元信息（类型、大小、修改时间、权限）。适用：下载前确认目标存在及其大小（超大文件先提醒用户）；判断目标是文件还是目录，以决定用 download_file 还是 download_dir（MVP）。path 为绝对路径；目标不存在时返回 not_found，此时可用 search_files 定位正确路径，不要反复尝试相近路径。`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "文件/目录的服务器绝对路径，以 / 开头" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["path"]
}
```

返回：`{ ok, path, type, size, mtime, perms }`

### 1.5 `download_file`

description：`下载服务器上的单个文件到本机暂存目录（~/.ft-ftp-mcp/staging/），返回本地文件路径、大小、修改时间与 SHA-256。拿到 local_path 后用本机文件读取能力打开处理即可，文件内容不进入对话上下文。remote_path 必须是单个文件（非目录）的服务器绝对路径：目标是目录时改用 download_dir（MVP）；只想看文本/CSV 的表头或前几行时优先用 read_text_preview（MVP），避免不必要的下载。路径不确定时先用 search_files 或 list_dir 定位并与用户确认，禁止凭猜测下载。单文件大小上限默认 2GB（按服务器配置），超限返回 size_limit_exceeded。`

```json
{
  "type": "object",
  "properties": {
    "remote_path": { "type": "string", "description": "远程文件的服务器绝对路径，以 / 开头，指向单个文件而非目录" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["remote_path"]
}
```

返回：`{ ok, local_path(暂存目录内路径), remote_path, size, mtime, sha256 }`
门控：单文件大小上限默认 2GB（按服务器配置），超限返回 `size_limit_exceeded`（PRD 5.3 ①）。

### 1.6 `upload_file`

description：`上传本机文件到服务器指定路径。local_path 为本机绝对路径（如 D:/data/report.csv）；remote_path 为服务器上的目标绝对路径（以 / 开头，含目标文件名）。安全规则：目标位置已存在同名文件时默认拒绝上传；确认目标文件无保留价值后，用户明确确认并显式传 overwrite=true 才允许覆盖。服务器处于 readOnly 模式或账号无写权限时返回语义化错误。上传成功返回远程路径、大小与 SHA-256，可用于校验传输完整性。上传前若不确定远程目录是否存在，可先用 list_dir 确认或 make_dir 创建。`

```json
{
  "type": "object",
  "properties": {
    "local_path": { "type": "string", "description": "本机源文件的绝对路径，如 D:/data/report.csv" },
    "remote_path": { "type": "string", "description": "远程目标的服务器绝对路径（以 / 开头，含目标文件名）" },
    "overwrite": { "type": "boolean", "description": "目标已存在同名文件时是否覆盖，默认 false（拒绝）。置 true 前须先取得用户确认", "default": false },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["local_path", "remote_path"]
}
```

返回：`{ ok, remote_path, size, sha256 }`
门控：jail 内；目标已存在且 `overwrite` 非 true -> 拒绝（`policy_rejected`，hint 固定文案"目标文件已存在，如需覆盖请与用户确认后显式传 overwrite: true 重新调用"）；`overwrite: true` 时允许覆盖；`readOnly` 服务器拒绝。

### 1.7 `make_dir`

description：`在服务器上创建目录，支持一次创建多级（父目录不存在时自动逐级创建）。path 为目录的服务器绝对路径（以 / 开头）。目录已存在时视为成功（幂等），created 为空列表。创建后常配合 upload_file 上传文件到该目录。readOnly 服务器或账号无写权限时拒绝。`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "要创建的目录服务器绝对路径，以 / 开头，如 /reports/analysis" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["path"]
}
```

返回：`{ ok, path, created: [逐级创建的路径列表，目录已存在时为空] }`
门控：jail 内；readOnly 拒绝。幂等语义为评审补充定义。

---

## 2. MVP 工具（6 个）

### 2.1 `read_text_preview`

description：`读取服务器上文本/CSV 文件的开头部分（默认前 100KB，可用 max_bytes 调整，上限 1MB），按完整行对齐截断，不劈行、不劈字符。内容编码按 BOM、UTF-8 严格解码、GBK 回退的顺序判定。适用：快速查看表头、样例行、文件格式，回答"这个文件有哪些列/前几行长什么样"类问题。返回值含 truncated、total_lines、returned_lines 与 hint 完整性上下文；文件未超预览上限时 total_lines 返回准确值，截断时返回 null，不为统计总行数读取整个文件。当 truncated 为 true 时，严禁基于预览片段回答涉及全文件的问题（统计、聚合、求和、精确匹配等），必须改用 download_file 下载后用本机能力分析。二进制文件（图片、压缩包等）不适用本工具，请直接 download_file。`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "文本文件的服务器绝对路径，以 / 开头" },
    "max_bytes": { "type": "integer", "description": "读取字节上限，默认 102400（100KB），最大 1048576（1MB），传入更大值会被钳制到 1MB", "default": 102400 },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["path"]
}
```

返回（完整性上下文，PRD 5.3 ⑩）：`{ ok, content, truncated, total_lines(截断时为 null), returned_lines, hint }`
行为要求：内容编码按 BOM → UTF-8 严格解码 → GBK 回退；截断按完整行对齐；未截断时 `total_lines` 为准确值，截断时为 null；`hint` 明确说明预览是否完整，截断时提示涉及全文件统计/聚合/精确查找的问题应改用 `download_file`。

### 2.2 `download_dir`

description：`递归下载服务器上整个目录（含全部子目录）到本机暂存目录，返回汇总统计（本地目录路径、文件数、总大小、跳过项与失败清单），不逐文件罗列。remote_path 必须是目录（非单个文件）的服务器绝对路径；只下载单个文件请用 download_file。批次受服务器 max_batch_files 与 max_batch_total_bytes 双上限约束，每个文件另受 max_file_size_bytes 限制；批次超限时整体拒绝。max_files 只能调低，传入更大值钳制到服务器上限。空目录保留；软链接默认跳过并计入 skipped；传输按开始时的目录枚举快照执行。单文件失败不中断整批，失败项在 failed 清单中汇报，由用户决定重试哪些。`

```json
{
  "type": "object",
  "properties": {
    "remote_path": { "type": "string", "description": "远程目录的服务器绝对路径，以 / 开头，指向目录而非文件" },
    "max_files": { "type": "integer", "description": "本次下载文件数上限，默认 500；只能调低，传更大值不会突破服务端硬上限", "default": 500 },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["remote_path"]
}
```

返回：`{ ok, local_dir, file_count, total_size, skipped: [{path, reason}], failed: [{path, error}] }`
门控：`max_batch_total_bytes`（默认 10GB）与 `max_batch_files`（默认 500）双上限；单文件同时受 `max_file_size_bytes` 限制。批次超限返回 `size_limit_exceeded` 并建议缩小范围。

### 2.3 `upload_dir`

description：`递归上传本机整个目录（含子目录）到服务器目标目录，目标目录不存在时自动创建，返回汇总统计（成功文件数、总大小、跳过项、失败清单），不逐文件罗列。同名文件默认拒绝覆盖；确认目标文件无保留价值后，用户明确确认并显式传 overwrite=true 才允许覆盖。批次受服务器 max_batch_files 与 max_batch_total_bytes 双上限约束，每个文件另受 max_file_size_bytes 限制；批次超限时整体拒绝。空目录保留；软链接默认跳过并计入 skipped；传输按开始时的目录枚举快照执行。只上传单个文件请用 upload_file。`

```json
{
  "type": "object",
  "properties": {
    "local_path": { "type": "string", "description": "本机源目录的绝对路径" },
    "remote_path": { "type": "string", "description": "远程目标目录的服务器绝对路径（以 / 开头），不存在时自动创建" },
    "overwrite": { "type": "boolean", "description": "远程同名文件是否覆盖，默认 false（拒绝）。置 true 前须先取得用户确认", "default": false },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["local_path", "remote_path"]
}
```

返回：`{ ok, remote_path, file_count, total_size, skipped: [{path, reason}], failed: [{path, error}] }`
门控：jail 内；服务器级文件数与总大小双上限；单文件大小上限；readOnly 拒绝。
**产品裁定**：`upload_dir` 与 `upload_file` 使用相同覆盖规则：默认拒绝，显式 `overwrite=true` 且已取得用户确认后允许覆盖。

### 2.4 `rename`

description：`重命名服务器上的文件或目录：只改名称，不改变所在目录位置。new_name 仅是新名称本身，不得包含路径分隔符 /（传入含路径的名称会返回 invalid_path）。若需要把文件挪到其他目录（即使同时改名），必须用 move 工具。目标名称已存在时统一拒绝，不覆盖既有对象；可先用 list_dir 查看。`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "原文件/目录的服务器绝对路径，以 / 开头" },
    "new_name": { "type": "string", "description": "新名称（仅名称本身，不含任何路径分隔符）" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["path", "new_name"]
}
```

返回：`{ ok, old_path, new_path }`
门控：jail 内；目标已存在时返回 `policy_rejected`；readOnly 拒绝。实现层与 move 共用 RNFR/RNTO（PRD 4.1 拆分说明）。

### 2.5 `move`

description：`将服务器上的文件或目录移动到新路径（可跨目录），to_path 为完整目标路径并包含移动后的文件/目录名。仅在同目录内改名、不挪位置时请用 rename 工具。from_path 与 to_path 均须在服务器 root 内。目标位置已存在时统一拒绝，不覆盖既有对象；可先用 get_file_info 探测。移动是元数据操作，不传输文件内容，大文件也能瞬间完成。`

```json
{
  "type": "object",
  "properties": {
    "from_path": { "type": "string", "description": "源的服务器绝对路径，以 / 开头" },
    "to_path": { "type": "string", "description": "目标的服务器绝对路径（含移动后的文件/目录名）" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["from_path", "to_path"]
}
```

返回：`{ ok, from_path, to_path }`
门控：两路径均须在 jail 内；目标已存在时返回 `policy_rejected`；readOnly 拒绝。

### 2.6 `delete`

description：`删除服务器上的文件或空目录，不可逆的破坏性操作。调用时必须显式传 confirm=true，缺省或为 false 时拒绝执行并返回 policy_rejected。目录删除仅限空目录，非空目录会被拒绝，需先清空其中内容。执行前必须向用户复述目标路径并取得明确同意，禁止在未经用户确认的情况下删除任何对象。删除前可用 get_file_info 确认目标与类型。`

```json
{
  "type": "object",
  "properties": {
    "path": { "type": "string", "description": "要删除的文件/空目录的服务器绝对路径，以 / 开头" },
    "confirm": { "type": "boolean", "description": "安全确认开关：必须显式传 true 才执行删除；传 false 或省略会被拒绝（取得用户同意后再传 true 重调）" },
    "server": { "type": "string", "description": "目标服务器别名（对应配置文件 servers 数组中的别名）。仅当用户明确提到某台服务器/别名，或环境配置了多台服务器且从上下文无法判断目标时传入；单服务器场景缺省即可，缺省使用默认服务器。" }
  },
  "required": ["path", "confirm"]
}
```

返回：`{ ok, path, type(被删对象类型 file|dir) }`
门控：`confirm: true` 强制（**schema 层只约束 type: boolean，true 校验在逻辑层**，拒绝时 hint 固定文案"删除需用户确认后显式传 confirm: true"，PRD 第六章）；仅空目录；jail 内；readOnly 拒绝。

---

## 3. 实现注意（研发评审输入）

### 3.1 JSON Schema 方言白名单（PRD 附录 D 已知坑 1）

- **允许**：`type`、`description`、`properties`、`required`、`items`、`default`、字符串值 `enum`
- **禁止**：`pattern`、`oneOf` / `allOf`、`patternProperties`、`$ref`、`format`、数值类 `minimum` / `maximum`、以及单值布尔 `enum: [true]` 之类"用校验器做业务门控"的写法。FastMCP/Pydantic 自动生成的 `anyOf` 与 `additionalProperties` 允许出现
- 一切参数级校验（路径绝对性、`new_name` 不含 `/`、大小/条数上限、confirm 必须为 true）在工具内部逻辑层实现并返回语义化错误；schema 只做类型层约束
- 每次改动 schema 后，须在 Claude Desktop 冒烟一次"首次调用"（PRD 7.2），确认校验器不吃掉调用

### 3.2 错误 envelope 实现要点

- `policy_rejected` / `not_found` / `invalid_path` 的 `hint` 必须含**可执行的下一步**（用哪个工具、传什么参数），这是模型能否一次修正成功的关键
- `retryable` 按 0.3 节逐类型表实现；`connection_unavailable` 只在内部自动重试 1 次失败后才返回，且恒为 `retryable: false`（PRD 5.3 ⑧）
- `server_error` 的 hint 写明"可重试一次，仍失败请停止并告知用户"，防无限循环

### 3.3 控量实现要点

- `list_dir` 500 条、`search_files` 50 条上限截断时必须置 `truncated: true` 并附 `hint`
- `download_dir.max_files` 服务端硬上限钳制：传入大于上限的值按上限执行，并在返回中说明实际生效值
- `read_text_preview.max_bytes` 传入大于 1MB 的值钳制到 1MB

### 3.4 已确认的实现约束

1. **`move` / `rename` 目标覆盖门控**：实现层探测目标存在即拒绝，避免 FTP RNFR/RNTO 的服务器差异造成静默覆盖。
2. `upload_file` / `upload_dir` 默认拒绝覆盖，显式 `overwrite=true` 且取得用户确认后允许覆盖。
3. `make_dir` 幂等语义（已存在视为成功）已回写 PRD。
4. `server_error` 的 `retryable: true`（限 1 次）已作为 PRD 5.3 ⑧ 的扩充回写。

### 3.5 description 迭代机制

所有 description 为 v0.3 定稿候选，随联调失败案例持续迭代——版本随代码走，不单独维护本草案为唯一事实（PRD 4.2 原则 4）。每次修改 description 后用"只看描述的模型能否选对工具、拼对参数"自检一遍。

## 版本记录

- v0.1（2026-09-04）：初稿，13 工具全量（PoC 7 + MVP 6）
- v0.2（2026-09-04）：独立评审修订——路径边界补强（相对/盘符路径处理规则）；`server` 参数显式落入全部 schema；移除 `enum:[true]` 方言隐患并建立 schema 关键字白名单；错误 envelope 增加 `retryable` 精确定义与逐类型行为表、防循环重试规则；全部 description 重写（补齐选用边界与相邻工具区分）；补 PRD 一致性（list_dir/get_file_info 权限字段）；评审补充项标注（upload_dir 覆盖门控、move/rename 覆盖警示、make_dir 幂等、server_error 重试语义）
- v0.3（2026-09-10）：开发前契约收口——允许 FastMCP 生成的 anyOf/additionalProperties；补 download_dir 必填参数；定稿文本预览编码和 total_lines；定稿批量双上限、空目录、软链接与枚举快照语义；按 QA BUG-001 明确任意 `..` 路径段均拒绝
