# ft-ftp-mcp-stdio

`ft-ftp-mcp-stdio` is a local MCP server for browsing and transferring files on FTP and SFTP servers. It runs over stdio, so an MCP client starts it as a child process and communicates through JSON-RPC on stdin/stdout. The server then uses native FTP or SFTP protocols to access configured remote file servers.

## Features

- FTP and SFTP support.
- MCP stdio transport, with no listening TCP port.
- Multiple logical server aliases in one local config file.
- Credentials loaded from the OS keyring or an environment variable, not from MCP tool arguments.
- Virtual absolute remote paths, mapped to a configured server root.
- Read-only server mode.
- Upload protections: default no-overwrite behavior, size limits, and temporary same-directory upload commits.
- Download staging to local disk instead of returning large file bodies through MCP.
- Text preview for UTF-8, UTF-8 BOM, and GBK content.
- Structured tool results and structured error payloads.

## Tools

The server exposes these MCP tools:

| Tool | Purpose |
| --- | --- |
| `list_servers` | List configured logical servers without connecting to remote hosts. |
| `test_connection` | Test connectivity and authentication. |
| `list_dir` | List one remote directory level. |
| `search_files` | Search recursively by filename pattern. |
| `get_file_info` | Return metadata for one remote object. |
| `read_text_preview` | Return the beginning of a text file. |
| `download_file` | Download one remote file to local staging. |
| `upload_file` | Upload one local file. |
| `make_dir` | Create a remote directory. |
| `rename` | Rename an object in the same directory. |
| `move` | Move a file or directory. |
| `delete` | Delete a file or empty directory. |
| `download_dir` | Recursively download a directory to local staging. |
| `upload_dir` | Recursively upload a local directory. |

## Requirements

- Python `>=3.12,<3.13`
- Windows is the currently verified platform.
- FTP/SFTP account credentials with an appropriately restricted server-side root or account permission set.

The code is written to keep most platform assumptions local, but non-Windows environments should be treated as unverified until tested.

## Install From Source

```powershell
git clone <repository-url>
cd ft-ftp-mcp-stdio
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Start the MCP server manually:

```powershell
.\.venv\Scripts\python.exe -m ft_ftp_mcp_stdio
```

Normally your MCP client starts this command for you.

## MCP Client Configuration

Generic stdio configuration:

```json
{
  "mcpServers": {
    "ft-ftp-mcp-stdio": {
      "command": "C:/path/to/python.exe",
      "args": ["-m", "ft_ftp_mcp_stdio"],
      "env": {
        "FASTMCP_SHOW_SERVER_BANNER": "false",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

Use the Python executable from the environment where this package is installed. On Windows, `PYTHONUTF8=1` helps keep stderr and diagnostics UTF-8 safe for strict MCP clients.

## Server Configuration

The default config path is:

```text
~/.ft-ftp-mcp/config.json
```

Override it with:

```text
FT_FTP_MCP_CONFIG
```

Minimal example:

```json
{
  "version": 2,
  "default_server": "ftp1",
  "staging_dir": "~/.ft-ftp-mcp/staging",
  "log_usage": true,
  "servers": [
    {
      "alias": "ftp1",
      "protocol": "ftp",
      "host": "ftp.example.com",
      "port": 21,
      "username": "your_user",
      "root": "/",
      "description": "Example read-only FTP server",
      "readOnly": true,
      "max_file_size_bytes": 2147483648,
      "encoding": "auto",
      "credential_env": null,
      "key_path": null,
      "host_key_fingerprint": null
    }
  ]
}
```

Important notes:

- `root` is the real server-side root mapped to the virtual MCP path `/`.
- `readOnly` defaults to `true`; set it to `false` only for accounts intended to write.
- `credential_env` names an environment variable containing the password or SFTP key passphrase.
- `key_path` enables SFTP private-key authentication.
- `host_key_fingerprint` pins an SFTP host key fingerprint. Without it, SFTP uses trust-on-first-use records in `known_hosts`.

## Credentials

Store credentials outside MCP conversations:

```powershell
.\.venv\Scripts\python.exe -m ft_ftp_mcp_stdio cred add <alias>
.\.venv\Scripts\python.exe -m ft_ftp_mcp_stdio cred list
.\.venv\Scripts\python.exe -m ft_ftp_mcp_stdio cred remove <alias>
```

Credential lookup prefers the OS keyring. If no keyring entry exists and `credential_env` is configured, the value is read from that environment variable.

## Operations

Useful local commands:

```powershell
# Interactive config wizard
.\.venv\Scripts\python.exe -m ft_ftp_mcp_stdio setup

# Read-only diagnostics
.\.venv\Scripts\python.exe -m ft_ftp_mcp_stdio doctor

# Diagnostics for one server alias
.\.venv\Scripts\python.exe -m ft_ftp_mcp_stdio doctor --server <alias>
```

Downloaded files are written under the configured `staging_dir`. The project does not currently clean staging automatically.

## Development

Run the local checks:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tests scripts
```

Live FTP/SFTP tests are optional and must be run only against an isolated, authorized test server:

```powershell
.\.venv\Scripts\python.exe -m pytest --live
```

Do not run live tests against production file servers.

## Security Model

- Passwords and private-key passphrases are not MCP tool arguments.
- Remote paths are virtual absolute paths and are checked before remote operations.
- Write tools reject read-only servers before connecting.
- Uploads default to no overwrite.
- `rename` and `move` reject existing targets.
- `delete` requires `confirm=true` and deletes only files or empty directories.
- SFTP host keys are pinned by explicit fingerprint or by trust-on-first-use.

See [SECURITY.md](SECURITY.md) for reporting guidance.

## Repository Contents

```text
src/          Python package
tests/        Unit, contract, CLI, and optional live tests
scripts/      Development and schema helper scripts
templates/    MCP client config templates
fixtures/     Non-sensitive test fixtures
docs/schema/  Machine-readable config and MCP tool schemas
docs/decisions/ Architecture decision records
```

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).
