# 配置文件规范（config.json）v0.5

> 适用于下一版本实现。机器约束以 `docs/schema/config.schema.json` 为准。

## 顶层结构

配置只接受 `version: 2`。`servers` 必须是非空数组；多服务器时必须设置指向有效 alias 的 `default_server`。`staging_dir` 必须是本机绝对路径或 `~` 路径，`log_usage` 默认为 `true`。未知字段拒绝加载。

版本 1 不自动迁移、不覆盖。用户必须先自行备份，并显式删除或替换旧配置后重新运行 setup。

## 服务器字段

| 字段 | 要求 |
| --- | --- |
| `alias` | 必填；字母开头，最长 64 字符，配置内唯一 |
| `description` | 可选非空字符串，最长 200 字符；不得放入秘密或连接细节 |
| `protocol` | `ftp` 或 `sftp`；不支持 FTPS |
| `host`、`username` | 必填非空字符串，不通过 MCP 工具返回 |
| `port` | 1..65535；FTP 默认 21，SFTP 默认 22 |
| `root` | 必填、规范化的服务器绝对路径；虚拟 `/` 映射到这里 |
| `readOnly` | 默认 `true`；仅显式 `false` 启用写操作 |
| `encoding` | `auto`、`utf-8` 或 `gbk`，仅影响 FTP 文件名 |
| `max_file_size_bytes` | 非负整数，默认 2 GiB；`0` 表示不限制；只限制上传单个文件 |
| `key_path` | 仅 SFTP；本机私钥路径 |
| `credential_env` | 可选凭据环境变量名；否则使用系统凭据管理器 |
| `host_key_fingerprint` | 可选 SFTP SHA-256 指纹；匹配后同步到独立 known-hosts |

配置 v2 不包含 `max_batch_files` 或 `max_batch_total_bytes`。上传和下载均没有客户端批次数量或总字节上限，下载也不受 `max_file_size_bytes` 限制。

## 虚拟路径

MCP 的 `path`、`remote_path`、`from_path` 和 `to_path` 都是虚拟绝对路径。虚拟 `/reports/a.csv` 在 `root=/srv/finance` 时映射为 `/srv/finance/reports/a.csv`。Agent 不读取或传入真实 root。

拒绝空路径、相对路径、反斜杠、NUL 和完整 `..` 段；`.` 段规范化。禁止删除、重命名或移动虚拟 `/`，也禁止把对象移动到 `/`。

## SFTP 信任状态

known-hosts 位于配置旁，按 `alias algorithm fingerprint` 保存。配置指纹或已有 TOFU 记录必须在发送密码或私钥签名前验证。首次 TOFU、配置指纹同步和后续更新使用跨进程锁、同目录临时文件和原子替换；损坏、重复、冲突、锁失败或持久化失败均 fail-closed。

## 示例

参见仓库根目录 `config.example.json`。凭据不得写入配置、文档或测试 fixture。
