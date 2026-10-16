#!/bin/bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_ROOT="$HOME/.ft-ftp-mcp"
if [ "$(uname -s)" != Darwin ]; then
    echo 'ERROR: This installer requires macOS.' >&2
    exit 2
fi
PYTHON="${FT_FTP_MCP_PYTHON:-python3.12}"
PACKAGE_ARCH="$("$PYTHON" - <<'PY'
import platform
import sys
import subprocess

if sys.version_info[:2] != (3, 12):
    raise SystemExit('ERROR: Python 3.12.x is required.')
if int(platform.mac_ver()[0].split('.')[0]) < 11:
    raise SystemExit('ERROR: macOS 11 or later is required.')
architecture = platform.machine()
if architecture not in {'arm64', 'x86_64'}:
    raise SystemExit(f'ERROR: Unsupported Python architecture: {architecture}')
if architecture == 'x86_64':
    translated = subprocess.run(['sysctl', '-in', 'sysctl.proc_translated'], capture_output=True, text=True)
    if translated.returncode == 0 and translated.stdout.strip() == '1':
        print('NOTICE: Python runs under Rosetta; selecting x86_64 dependencies. Use native arm64 Python for a native installation.', file=sys.stderr)
print(architecture)
PY
)"
echo "Selected Python architecture: $PACKAGE_ARCH"
(cd "$PACKAGE_DIR" && shasum -a 256 -c SHA256SUMS.txt)
VENV="$APP_ROOT/venv"
if [ -d "$VENV" ]; then
    "$VENV/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Existing environment must use Python 3.12"'
else
    "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" - "$PACKAGE_ARCH" <<'PY'
import platform
import sys
if platform.machine() != sys.argv[1]:
    raise SystemExit('ERROR: Existing virtual environment has a different architecture.')
PY
"$VENV/bin/python" -m pip --isolated install --no-index --only-binary=:all: \
    --find-links "$PACKAGE_DIR/wheels/common" \
    --find-links "$PACKAGE_DIR/wheels/$PACKAGE_ARCH" \
    --require-hashes -r "$PACKAGE_DIR/requirements-$PACKAGE_ARCH.txt"
"$VENV/bin/python" -m pip --isolated check
"$VENV/bin/python" - "$PACKAGE_DIR" "$VENV/bin/python" "$APP_ROOT/templates" <<'PY'
import importlib.metadata
import json
import sys
import tomllib
from pathlib import Path

package, executable, destination = sys.argv[1:]
source = Path(package)
assert importlib.metadata.version('ft-ftp-mcp-stdio') == (source / 'VERSION.txt').read_text().strip()
target = Path(destination)
target.mkdir(parents=True, exist_ok=True)
for name in ('codex-config.toml', 'workbuddy-mcp.json'):
    text = (source / 'templates' / (name + '.template')).read_text(encoding='utf-8')
    text = text.replace('{{VENV_PYTHON}}', json.dumps(executable, ensure_ascii=False)[1:-1])
    if name.endswith('.json'):
        json.loads(text)
    else:
        tomllib.loads(text)
    (target / name).write_text(text, encoding='utf-8')
print(f'Installed. MCP templates: {target}')
PY
echo "Configure servers: \"$VENV/bin/python\" -m ft_ftp_mcp_stdio setup"
echo "Diagnose: \"$VENV/bin/python\" -m ft_ftp_mcp_stdio doctor"
