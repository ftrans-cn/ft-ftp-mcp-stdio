# DSH Market 发布记录

适配包：`dsh-ft-ftp@0.1.0`。产品运行时：`ft-ftp-mcp-stdio@0.3.1`。兼容 DSH 0.2.2-rc.1，Node >=24.9。更新日期：2026-11-17。

## 发布状态

- 代码已推送：[提交 cfe8cec](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/commit/cfe8cecb5a22ea2f1b1edb9492ef7a869c34622b)，适配源目录 `integrations/dsh`。
- GitHub 插件包已发布：[dsh-v0.1.0 Release](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/releases/tag/dsh-v0.1.0)，包含 tarball 和 SHA-256 校验文件，独立于产品 0.3.1 的离线 zip。
- npm：账号所有者完成认证后，已发布 [dsh-ft-ftp@0.1.0](https://www.npmjs.com/package/dsh-ft-ftp/v/0.1.0)。官方 registry 的版本、SHA-512 完整性和 tarball SHA-256 均与验证包一致。
- DSH Market：已提交 [收录申请 #52](https://github.com/tjsdyy/dshplugin/issues/52)，当前待审核，尚不能标记为市场已收录。当前市场仓库不存在 README 所提及的 plugin-submission 标签，已在申请中注明，由维护者分流。

GitHub Release tarball SHA-256：`a801d5a208eace06850a7f133c48141dceca9f9777b1bb8c36ce594148146023`。

已使用 GitHub CLI 从 Release 下载回产物并核对 SHA-256，在全新隔离 DSH profile 安装该下载文件，14 个工具及 list_servers 验证通过。本机网络通过直接下载 URL 安装曾出现连接重置；这一路径尚未在本机验证通过。遇到同样网络问题时，可先运行 `gh release download dsh-v0.1.0 --repo ftrans-cn/ft-ftp-mcp-stdio --pattern dsh-ft-ftp-0.1.0.tgz`，再按安装说明添加本地文件。

推荐 CLI 安装指令：`dsh plugin --profile web add dsh-ft-ftp@0.1.0`。桌面用户在插件管理页面输入 `dsh-ft-ftp@0.1.0` 安装；不要使用 CLI 修改 desktop profile。

发布后曾遇到 registry CDN 对新 tarball 的短暂 404 缓存（300 秒）；带查询参数的独立下载可获取正确产物，缓存过期后，全新隔离 DSH profile 按标准 npm 包名安装成功，14 个工具注册及 list_servers 实际调用通过。

## 安装及验证

Windows / macOS 共用 [插件安装说明](../integrations/dsh/README.md)。原有 Windows / macOS 独立产品手册以及 Codex / WorkBuddy 手动安装继续有效。

本地验证、实际桌面 Host 验证和 macOS / SFTP 验证边界见 [适配验证记录](DSH-Market-适配验证.md)。市场或 GitHub 的收录不能代替实际运行测试。

## npm 发布与后续维护

1. 维护者通过本机 npm 浏览器登录完成发布权限认证；不要把 Token 写入代码、文档或聊天。
2. 使用通过验证的 tarball 执行 `npm publish <tarball绝对路径> --access public --registry https://registry.npmjs.org/`；如 npm 要求二次认证，在本机交互完成。
3. 通过 `npm view dsh-ft-ftp@0.1.0 dist.integrity --registry https://registry.npmjs.org/` 核验版本和完整性，再在全新 DSH profile 从 registry 安装并验证工具。
4. 市场条目优先使用 npm 安装指令；npm 尚不可用时可提交 GitHub Release tarball URL 安装指令，并明确该状态。不要使用项目根目录的 `github:ftrans-cn/ft-ftp-mcp-stdio`：根目录不是 DSH bundle。
5. 后续升级适配包须更新版本、兼容范围、验证和发布记录。npm 已发布版本不可覆盖；必要时停用有问题版本并发布修正版。GitHub 代码可通过新提交回退，用户可从插件管理器禁用插件，原独立产品不受影响。
