# FT Agent FTP 插件当前 Spec 基线

> 状态：Current（实现及独立代码审查完成）
> 基线日期：2026-09-23
> 产品版本：`ft-ftp-mcp-stdio 0.3.0`
> 实现起点：`1e816078458b41ea2a7518a8561aa6558ee2daf4`
> 适用范围：MCP stdio 服务及其 14 个 FTP/SFTP 文件工具

## 1. 文档定位

本文记录当前已经实现并通过候选验证的行为。完整规范性要求采用
[`docs/spec/changes/next-development.md`](changes/next-development.md) 中已接受的第 2 至 19 节；
该变更 Spec、有效 ADR、正式 Schema与本文共同构成当前契约，不再以历史 Schema 草案或
2026-09-20 的 13 工具基线作为当前事实。

- 正式机器契约：`docs/schema/mcp-tools.json`。
- 配置机器契约：`docs/schema/config.schema.json`。
- 设计取舍与残余风险：`docs/decisions/` 及已接受变更 Spec 第 19 节。
- 候选验证证据：`docs/development/plans/next-development.md` 第 13 至 15 节。

变更 Spec 中的产品行为、安全边界、错误语义和已接受残余风险自本基线起均为当前行为。
实现与独立代码审查已经完成，完整证据由执行清单和代码审查报告保存。

## 2. 当前能力

- 服务通过 stdio 暴露 14 个静态 MCP Tools，不提供 Resources 或 Prompts。
- 支持 FTP 与 SFTP；不支持 FTPS。
- 新增 `list_servers`，仅读取本地配置，不连接服务器、不读取凭据、不触发 TOFU。
- 其余 13 个工具覆盖连接测试、浏览、搜索、元信息、文本预览、单文件和目录传输、创建目录、
  重命名、移动与删除。
- 所有远程路径均为以 `/` 开头、相对于配置 root 的虚拟绝对路径；Agent 不接触真实 root。
- 凭据来自本机 keyring 或配置指定的环境变量，不作为工具参数或工具结果返回。
- 配置只接受 `version:2`；`root` 必填，`readOnly` 缺省为 `true`，不自动迁移或覆盖 v1 配置。

## 3. Schema 与 MCP 线级契约

- `docs/schema/mcp-tools.json` 从运行时 `tools/list` 生成，是唯一正式工具 Schema 快照。
- 14 个工具均具有非空 title、description、字段描述、封闭 inputSchema、精确 outputSchema 和
  MCP annotations。
- 成功结果与统一业务错误均由根级 object 内部的 `oneOf` 表达。
- 工具运行时错误返回 `isError=true` 和结构化错误体；框架参数错误返回 `isError=true` 且
  `structuredContent=null`。
- 错误类型是封闭枚举；仅 `size_limit_exceeded` 和 `outcome_unknown` 允许受控 `details`。
- 对外失败固定 `retryable:false`，不得泄露 host、port、username、真实 root、凭据、密钥路径、
  指纹或底层异常文本。
- 当前框架契约锁定 FastMCP 4.0.2、MCP SDK/mcp-types 2.1.1；升级时必须重跑能力探针。

## 4. 路径与链接安全

- 远程路径拒绝空值、相对路径、反斜杠、NUL 和完整 `..` 段，并在映射后再次验证 root 边界。
- 虚拟 `/` 不允许删除、重命名或作为移动源/目标。
- 远端目录项名称是不可信输入；递归、批量和本地落盘均执行组件及逃逸检查。
- SFTP 从 root 开始逐段 `lstat`，发现符号链接即拒绝或在批量中跳过；检查不可靠时 fail-closed。
- FTP 仅在协议元数据能够识别链接时拒绝；无法可靠识别时依赖服务端隔离边界。
- 本地上传拒绝 symlink、junction 和 reparse point，并在枚举、打开前及句柄层复核。

## 5. 主机密钥与连接副作用

- SFTP 在发送认证材料前完成配置指纹或 known-hosts/TOFU 校验。
- known-hosts 使用 alias 身份、跨进程互斥、同目录临时文件和原子替换；损坏、冲突、锁定或安全
  持久化失败时 fail-closed。
- 只有 `list_servers` 的 `readOnlyHint=true`。其他读取工具可能因首次 SFTP 连接写入 TOFU 状态，
  因此 annotations 中的 `readOnlyHint=false` 不表示它们会修改远端业务数据。

## 6. 传输、批量与恢复

- `max_file_size_bytes` 只限制上传的单个普通文件，默认 2 GiB，`0` 表示不限制。
- 不设置客户端批量文件数或总字节上限；下载也不受单文件大小限制。
- 上传先写入同目录随机临时对象，再提交到最终目标；临时名使用至少 64 位随机量并在使用前检查。
- `overwrite=false` 的首次目标存在性检查构成授权快照；不承诺提交时并发无覆盖，相关风险已接受。
- 写操作发生连接异常后不得盲目重放。只有能够证明请求尚未开始或满足规范成功证据时才恢复；
  无法判断时返回 `outcome_unknown`。
- `upload_dir` 单项不确定时总体状态为 `indeterminate`，调用方不得整体重试。
- 下载失败、取消或连接异常会清理本次部分文件；已知远端大小时校验落盘大小与可观察来源变化。
- 批量结果使用封闭状态和逐项虚拟路径；恶意目录项、链接、超限与失败按规范跳过或失败并继续。

## 7. 文本、时间与输出最小化

- `read_text_preview.max_bytes` 允许 1 至 1048576，范围错误在工具运行时返回结构化
  `policy_rejected`，不静默钳制。
- 文本预览支持 UTF-8、UTF-8 BOM 和 GBK；截断到不完整行时返回内容并标记
  `partial_line=true`，`total_lines=null`。
- 可确定的 FTP/SFTP `mtime` 统一为带时区的 ISO 8601；不能可靠解析时返回 `null`。
- `test_connection` 只返回逻辑 alias、协议和只读状态；`list_servers` 只返回逻辑服务器摘要。
- 成功结果、错误、批量明细和 Agent 可见日志均不得暴露真实服务器路径或连接敏感信息。

## 8. 已验证宿主与非目标

- 正式支持宿主为 Codex 和 WorkBuddy。候选验证覆盖真实工具发现、调用前参数拒绝、
  结构化运行时错误和模型侧可取得的稳定错误字段；框架能力探针同时验证 annotations 与线级语义。
- 非目标包括 FTPS、断点续传、事务式批量操作、异步长任务、全局速率/并发限制、服务端总执行
  超时、staging TTL/配额/自动清理和本地上传允许根目录白名单。
- 所有已接受残余风险继续以变更 Spec 第 19 节为准，不因候选验证而视为已解决。
