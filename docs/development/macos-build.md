# macOS 通用离线包构建

用户安装步骤统一维护在 [macOS 安装手册](../FTP-MCP-快速安装手册-macOS-v0.3.1.md)。

使用含 pip、packaging 的 Python 3.12，确保 uv 在 PATH，在仓库根目录执行：

```text
python scripts/build_macos_package.py
```

脚本在 Windows 上下载和校验两个架构的 wheel，不执行 macOS 二进制。
产物为 `release/0.3.1/ft-ftp-mcp-stdio-offline-0.3.1-py312-macos.zip`，
附外部 SHA-256。同名已有产物不会被覆盖。Python 安装器不包含在 ZIP 内。

共用 wheel 按文件名及完整字节比较后仅存一份，位于 `wheels/common`；
其他 wheel 分别位于 `wheels/arm64`、`wheels/x86_64`。
每个架构拥有独立版本与哈希清单。安装脚本根据 Python 实际架构选择
对应清单及目录，不会将另一架构的 wheel 暴露给 pip。

依赖来自 uv.lock。Intel 通过 `scripts/requirements-macos-x86_64.txt`
覆盖 cryptography 至 48.0.1，arm64 沿用 50.0.1；两种依赖闭包分别校验。
构建信息记录基础锁哈希、兼容锁哈希、构建脚本哈希和每架构验证结果。

安装脚本检查 macOS 11+、Python 3.12、受支持架构、已有 venv 架构与
包内哈希。Rosetta 下 x86_64 Python 会显示提示并选择 x86_64 依赖。
已有 venv 架构不一致时停止，不自动删除环境或配置。

Windows 静态构建、依赖闭包与脚本分支测试不能替代真实 Mac 上的
安装、Keychain 和 FTP/SFTP/MCP 联调。当前尚未完成该实机验收。
