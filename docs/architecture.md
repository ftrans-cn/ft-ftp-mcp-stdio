# Architecture

`ft-ftp-mcp-stdio` is a local, single-user MCP server. An MCP client starts it as a stdio child process, then calls file tools over JSON-RPC. The server reads local configuration and credentials, connects to the selected FTP or SFTP server, performs the operation, closes the connection, and returns structured MCP content.

```text
User
  -> MCP client
    -> ft-ftp-mcp-stdio over stdio
      -> FileService
        -> FTPDriver or SFTPDriver
          -> remote FTP/SFTP server
```

## Boundaries

Inside this project:

- MCP tool registration and structured responses.
- Local configuration parsing.
- Credential lookup from keyring or environment variables.
- Virtual remote path validation.
- Read/write policy checks.
- FTP and SFTP file operations.
- Download staging and usage logging.
- CLI helpers for setup, credentials, and diagnostics.

Outside this project:

- Natural-language planning by the MCP client.
- Final approval UI provided by the MCP client.
- FTP/SFTP account provisioning.
- Server-side file permissions, quotas, backups, and auditing.
- Operating-system credential store security.

## Main Modules

| Module | Responsibility |
| --- | --- |
| `server.py` | Creates the FastMCP server, registers tools, wraps results and errors. |
| `service.py` | Orchestrates file operations, policy checks, retries, and result construction. |
| `config.py` | Loads and validates v2 JSON configuration. |
| `credentials.py` | Resolves passwords or private-key passphrases from keyring or env vars. |
| `paths.py` | Maps virtual paths to configured remote roots and rejects invalid paths. |
| `drivers/base.py` | Defines the common FTP/SFTP driver protocol. |
| `drivers/ftp.py` | Implements FTP behavior with `ftplib`. |
| `drivers/sftp.py` | Implements SFTP behavior with Paramiko and host-key verification. |
| `known_hosts.py` | Stores SFTP trust-on-first-use records. |
| `usage_log.py` | Writes best-effort local JSONL usage logs. |
| `cli.py` | Dispatches `setup`, `doctor`, and credential commands. |

## Tool Call Flow

```text
MCP tools/call
  -> FastMCP argument binding
  -> server wrapper
  -> load config
  -> select explicit or default server
  -> validate paths and policy
  -> resolve credentials
  -> create FTP/SFTP driver
  -> connect and execute operation
  -> close connection
  -> record usage log
  -> return structured content
```

The server does not maintain a long-lived FTP/SFTP session pool. Each tool call owns its connection lifecycle.

## Configuration

The default configuration file is `~/.ft-ftp-mcp/config.json`. The `FT_FTP_MCP_CONFIG` environment variable can point to another file.

Configuration contains non-secret connection metadata: alias, protocol, host, port, username, root, read-only flag, encoding, optional SFTP key path, and optional host-key fingerprint. Passwords and SFTP key passphrases are stored separately.

## Path Model

Tool arguments use virtual absolute paths such as `/reports/today.csv`. The configured server `root` maps virtual `/` to a real remote path.

The service rejects paths that are not absolute, contain parent segments, use backslashes, or otherwise escape the configured root. SFTP additionally checks path segments with `lstat` to reject symlink traversal where possible. FTP support depends more heavily on server behavior and account restrictions.

## Transfer Model

Downloads are written to local staging. Tool responses return paths, metadata, and hashes instead of embedding full file bodies.

Uploads write to a temporary object in the target directory and then commit to the final path. Uploads default to no overwrite. Directory transfers use best-effort semantics and report skipped, failed, or indeterminate items rather than pretending to be transactional.

## Security Model

- Credentials are not MCP tool arguments.
- Read-only servers reject write tools before remote connection.
- `upload_file` and `upload_dir` default to no overwrite.
- `rename` and `move` reject existing targets.
- `delete` requires `confirm=true`.
- SFTP host keys are checked before authentication.
- Usage logs do not store credentials or file contents, but paths and aliases can still be sensitive.

## Known Limits

- FTPS is not implemented.
- Transfers are synchronous.
- There is no global concurrency limiter.
- There is no automatic staging cleanup.
- Batch upload/download operations are not transactional.
- Non-Windows platforms are not yet verified.

