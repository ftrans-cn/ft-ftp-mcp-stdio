# Contributing

Thanks for your interest in improving `ft-ftp-mcp-stdio`.

## Development Setup

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Checks

Run these before opening a pull request:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\ruff.exe check .
.\.venv\Scripts\mypy.exe src tests scripts
```

Live tests require explicit authorization and an isolated FTP/SFTP test environment:

```powershell
.\.venv\Scripts\python.exe -m pytest --live
```

Do not run live tests against production servers.

## Guidelines

- Keep credentials out of source, docs, tests, logs, and examples.
- Prefer structured config/schema changes over ad-hoc parsing.
- Update tests when public tool behavior changes.
- Update `docs/schema/mcp-tools.json` if MCP tool contracts change.
- Do not commit release packages, wheelhouses, staging files, or local runtime state.

