# FT FTP MCP 发布记录

产品及 npm 包名：`ft-ftp-mcp-stdio`。版本：`0.3.1`。更新日期：2026-11-17。

## 当前状态

- Python 产品 0.3.1：已提供 Windows / macOS 安装包，见 [产品发布页](https://github.com/ftrans-cn/ft-ftp-mcp-stdio/releases/tag/tag_v0.3.1)。
- npm 包 0.3.1：已正式发布至 [npm](https://www.npmjs.com/package/ft-ftp-mcp-stdio/v/0.3.1)，官方 registry 元数据及包完整性已核验。
- 源码及文档同步目标：[GitLab](https://gitlab.ftrans.cn/ftrans/ft-ftp-mcp-stdio) 与 [GitHub](https://github.com/ftrans-cn/ft-ftp-mcp-stdio)。
- 本机 Harness Desktop：已通过官方 pluginManager 按 npm 包名从官方 registry 安装 0.3.1；14 个工具注册、配置发现、连接测试和目录读取通过。
- DSH Market：正式版本尚待收录审核，npm 发布与 Harness 安装成功不代表已上架市场。

## 发布完整性

- tarball SHA-256：`edea7da72ccb485c6f7c20307d0d4121095e328094459523b37e30be5839c8ba`。
- npm dist.integrity：`sha512-zAXa5hwnxcYw7dHQU6508htUUKlMVfz9pgQ7Kem6/FQhuzlPz57JyzpUdEo+2AAsRmCvBHbieJL9UZ0dOgrh2w==`。
- Desktop 依赖及锁文件记录 registry 版本 0.3.1 及上述完整性；安装请求未使用本地 tarball。临时验证入口已移除，原 profile patch 已恢复，正式插件依赖保留。

## 安装说明

参阅 [FT FTP MCP 安装说明](../integrations/dsh/README.md)及 [验证记录](DSH-Market-适配验证.md)。Codex / WorkBuddy 继续按产品手册完成手动安装；DSH 使用 npm 包，运行前需安装 Python 3.12 产品运行时。

## 正式发布步骤

1. 完成 README 评审，将审核通过的源码和文档推送到 GitHub。
2. 在仓库根目录执行 `npm pack ./integrations/dsh --pack-destination ./release`，核验包名、版本、README、入口及文件清单。
3. 将该 tarball 发布到官方 registry，并完成 npm 要求的本机账号认证。
4. 使用 `npm view ft-ftp-mcp-stdio@0.3.1 dist.integrity --registry https://registry.npmjs.org/` 核验完整性，再从 registry 安装到全新 DSH profile，验证工具注册和实际调用。
5. 发布正式下载包，提交市场收录申请，并回填实际链接及审核状态。

已发布的 npm 版本不可覆盖。后续修正应使用新的版本号。禁用或卸载 DSH 插件会保留 Python 产品运行时、配置、系统凭据及 Codex / WorkBuddy 配置。
