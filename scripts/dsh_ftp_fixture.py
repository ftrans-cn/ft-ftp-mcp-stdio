"""Disposable localhost FTP fixture for verify_dsh.mjs; never reads user config."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


def main() -> None:
    root = Path(sys.argv[1])
    remote = root / "remote"
    remote.mkdir(parents=True, exist_ok=True)
    (remote / "hello.txt").write_text("Hello DSH / 中文\n", encoding="utf-8")
    authorizer = DummyAuthorizer()
    authorizer.add_user("fixture", "disposable-test-only", str(remote), perm="elradfmwMT")
    handler = type("FixtureHandler", (FTPHandler,), {"authorizer": authorizer})
    server = FTPServer(("127.0.0.1", 0), handler)
    port = server.socket.getsockname()[1]
    entry = {
        "alias": "fixture", "protocol": "ftp", "host": "127.0.0.1", "port": port,
        "username": "fixture", "root": "/", "readOnly": False, "encoding": "utf-8",
        "credential_env": "FT_FTP_DSH_TEST_PASSWORD",
    }
    config = root / "ftp.json"
    config.write_text(json.dumps({
        "version": 2, "servers": [entry, {**entry, "alias": "readonly", "readOnly": True}],
        "default_server": "fixture", "staging_dir": str(root / "staging"), "log_usage": False,
    }), encoding="utf-8")
    print(json.dumps({"configPath": str(config)}), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
