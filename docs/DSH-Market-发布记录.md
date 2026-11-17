# DSH Market 发布记录

适配包：`dsh-ft-ftp@0.1.0`。产品运行时：`ft-ftp-mcp-stdio@0.3.1`。兼容 DSH 0.2.2-rc.1，Node >=24.9。更新日期：2026-11-17。

## 发布状态

- 代码目标：[ftrans-cn/ft-ftp-mcp-stdio](https://github.com/ftrans-cn/ft-ftp-mcp-stdio)，适配源目录 `integrations/dsh`。
- GitHub 插件包发布目标：`dsh-v0.1.0` Release，tarball 独立于产品 0.3.1 的离线 zip。
- npm：发布前检查未登录官方 registry；等待本机 `npm login --registry https://registry.npmjs.org/` 授权。未发布时不能用 npm 包名安装。
- DSH Market：待提交；提交成功后记录实际 Issue URL，审核后才可标记为市场已收录。

## 安装及验证

Windows / macOS 共用 [插件安装说明](../integrations/dsh/README.md)。原有 Windows / macOS 独立产品手册以及 Codex / WorkBuddy 手动安装继续有效。

本地验证、实际桌面 Host 验证和 macOS / SFTP 验证边界见 [适配验证记录](DSH-Market-适配验证.md)。市场或 GitHub 的收录不能代替实际运行测试。

## npm 发布与后续维护

1. 维护者通过本机 npm 浏览器登录完成发布权限认证；不要把 Token 写入代码、文档或聊天。
2. 使用通过验证的 tarball 执行 `npm publish <tarball绝对路径> --access public --registry https://registry.npmjs.org/`；如 npm 要求二次认证，在本机交互完成。
3. 通过 `npm view dsh-ft-ftp@0.1.0 dist.integrity --registry https://registry.npmjs.org/` 核验版本和完整性，再在全新 DSH profile 从 registry 安装并验证工具。
4. 市场条目优先使用 npm 安装指令；npm 尚不可用时可提交 GitHub Release tarball URL 安装指令，并明确该状态。不要使用项目根目录的 `github:ftrans-cn/ft-ftp-mcp-stdio`：根目录不是 DSH bundle。
5. 后续升级适配包须更新版本、兼容范围、验证和发布记录。npm 已发布版本不可覆盖；必要时停用有问题版本并发布修正版。GitHub 代码可通过新提交回退，用户可从插件管理器禁用插件，原独立产品不受影响。
