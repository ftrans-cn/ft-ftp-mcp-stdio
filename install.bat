@echo off
setlocal EnableExtensions

set "APP_ROOT=%LOCALAPPDATA%\ft-ftp-mcp"
set "VENV_DIR=%APP_ROOT%\venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "TEMPLATE_SOURCE=%~dp0templates"
set "TEMPLATE_DEST=%APP_ROOT%\templates"
set "PYTHON_EXE="
set "PYTHON_ARGS="
set "PACKAGE_VERSION="

where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_EXE=py"
        set "PYTHON_ARGS=-3.12"
    )
)

if not defined PYTHON_EXE (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE goto :python_missing
if not exist "%~dp0VERSION.txt" goto :version_missing
set /p PACKAGE_VERSION=<"%~dp0VERSION.txt"
"%PYTHON_EXE%" %PYTHON_ARGS% -c "import re,sys; raise SystemExit(0 if re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', sys.argv[1]) else 1)" "%PACKAGE_VERSION%" >nul 2>&1
if errorlevel 1 goto :version_invalid

if exist "%VENV_DIR%\" (
    if not exist "%VENV_PYTHON%" goto :venv_invalid
    "%VENV_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>&1
    if errorlevel 1 goto :venv_invalid
) else (
    "%PYTHON_EXE%" %PYTHON_ARGS% -m venv "%VENV_DIR%"
    if errorlevel 1 goto :failed
)

"%VENV_PYTHON%" -m pip install --upgrade --no-index --find-links "%~dp0wheels" ft-ftp-mcp-stdio==%PACKAGE_VERSION%
if errorlevel 1 goto :failed
"%VENV_PYTHON%" -c "import importlib.metadata,sys; raise SystemExit(0 if importlib.metadata.version('ft-ftp-mcp-stdio') == sys.argv[1] else 1)" "%PACKAGE_VERSION%"
if errorlevel 1 goto :failed

if not exist "%TEMPLATE_SOURCE%\workbuddy-mcp.json.template" goto :templates_missing
if not exist "%TEMPLATE_SOURCE%\codex-config.toml.template" goto :templates_missing
if not exist "%TEMPLATE_DEST%" mkdir "%TEMPLATE_DEST%"
if errorlevel 1 goto :failed

set "VENV_PYTHON_FORWARD=%VENV_PYTHON:\=/%"
powershell.exe -NoProfile -Command "$ErrorActionPreference='Stop'; $s=$env:TEMPLATE_SOURCE; $d=$env:TEMPLATE_DEST; $v=$env:VENV_PYTHON_FORWARD; [IO.File]::WriteAllText((Join-Path $d 'workbuddy-mcp.json'), [IO.File]::ReadAllText((Join-Path $s 'workbuddy-mcp.json.template'), [Text.Encoding]::UTF8).Replace('{{VENV_PYTHON}}',$v), (New-Object Text.UTF8Encoding($false))); [IO.File]::WriteAllText((Join-Path $d 'codex-config.toml'), [IO.File]::ReadAllText((Join-Path $s 'codex-config.toml.template'), [Text.Encoding]::UTF8).Replace('{{VENV_PYTHON}}',$v), (New-Object Text.UTF8Encoding($false)))"
if errorlevel 1 goto :failed

"%VENV_PYTHON%" -c "import json, os, pathlib, tomllib; p=pathlib.Path(os.environ['TEMPLATE_DEST']); json.loads((p/'workbuddy-mcp.json').read_text(encoding='utf-8')); tomllib.loads((p/'codex-config.toml').read_text(encoding='utf-8')); assert '{{VENV_PYTHON}}' not in (p/'workbuddy-mcp.json').read_text(encoding='utf-8'); assert '{{VENV_PYTHON}}' not in (p/'codex-config.toml').read_text(encoding='utf-8')"
if errorlevel 1 goto :failed

echo.
echo Installation complete.
echo Generated client templates: %TEMPLATE_DEST%
echo 1. Merge the generated template into your Agent client configuration.
echo 2. Configure the FTP/SFTP server: "%VENV_PYTHON%" -m ft_ftp_mcp_stdio setup
echo 3. Restart the Agent client and run an MCP smoke test.
exit /b 0

:python_missing
echo ERROR: Python 3.12.x was not found through py -3.12 or python.
echo Install the Windows x64 Python 3.12 release from https://www.python.org/downloads/
exit /b 2

:venv_invalid
echo ERROR: %VENV_DIR% exists but is damaged or does not use Python 3.12.x.
echo Delete that directory manually, then run this installer again.
exit /b 3

:templates_missing
echo ERROR: Required client templates are missing from %TEMPLATE_SOURCE%.
exit /b 4

:version_missing
echo ERROR: Required VERSION.txt is missing from the package.
exit /b 5

:version_invalid
echo ERROR: VERSION.txt does not contain a valid release version.
exit /b 6

:failed
echo ERROR: Offline installation failed.
exit /b 1
