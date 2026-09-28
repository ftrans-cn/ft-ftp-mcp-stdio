# Spec 目录说明

本目录管理 `ft-ftp-mcp-stdio` 的当前行为基线和后续契约变更。

## 文档结构

```text
docs/spec/
  README.md
  current.md
  changes/
    next-development.md
```

- `current.md`：当前已经实现并可验证的行为语义基线，是理解现行 MCP 服务与工具行为的首要文档。
- `changes/*.md`：单轮研发的增量 Spec，描述拟议变化、兼容影响和验收标准。
- `../schema/mcp-tools.json`：当前正式工具 Schema，是工具名称、描述、输入和输出 Schema 的机器可读契约。
- 长期架构决策仍按项目约定存放在 `docs/decisions/`，不与变更 Spec 混放。

## 生命周期

1. 开发前创建或填写一份变更 Spec，状态设为 `Draft`。
2. 评审通过后将状态改为 `Accepted`，再据此修改实现、测试和相关文档。
3. 开发完成后，根据实际运行时行为更新 `current.md`，并从代码生成或校验正式工具 Schema。
4. 验收通过后将变更 Spec 标记为 `Implemented`；取消或被替代时分别标记为 `Cancelled` 或 `Superseded`。
5. 已归档的变更 Spec 仅用于解释历史，不作为当前调用依据。

## 维护规则

- 基线只描述当前成立的契约，不混入未实施建议或路线图。
- 变更 Spec 只描述相对于基线的增量，不复制整份基线。
- 工具名称、参数、返回结构、错误语义或副作用发生变化时，必须同步更新实现、测试、正式 Schema 和 `current.md`。
- 简单缺陷修复或纯内部重构若不改变公共契约，可以不单独创建变更 Spec。
- 同一事实只保留一个完整定义。工具行为语义以 `current.md` 为准，机器可读工具接口以 `docs/schema/mcp-tools.json` 为准，配置字段以 `docs/配置文件规范（config.json）_v0.4.md` 为准，安装和操作以用户手册及 CLI 手册为准。
- `docs/MCP工具Schema草案_v0.3.md` 是历史开发草案，不再作为当前工具契约或测试基准。
- 若基线、正式 Schema、代码和测试发生冲突，应将其作为契约偏差处理；不得默认为其中任意一方天然正确。先依据已接受的变更 Spec 和验收结论确定正确行为，再同步其余材料。

## Schema 管理关系

- 变更 Spec 在开发前定义工具 Schema 应如何变化。
- 复杂接口变更可以在对应变更目录附带 `proposed-schema.json`；它是草案，不得用于运行时或发布。
- 正式 Schema 应在实现完成后从代码自动生成，并作为唯一有效的机器契约。
- `docs/schema/mcp-tools.json` 是从运行时 `tools/list` 生成的正式工具 Schema 快照；使用 `uv run python scripts/export_mcp_schema.py` 重建，并由测试检查是否与代码一致。
- 正式 Schema 不直接手工编辑；工具接口变更应先更新变更 Spec，再修改代码并重新生成该文件。
- `docs/schema/config.schema.json` 提供配置文件的机器可读基础约束；别名唯一性、`default_server` 引用和文件系统相关约束仍以运行时校验为准。
