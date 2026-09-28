from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import keyring
import pytest

from ft_ftp_mcp_stdio import cli, server
from ft_ftp_mcp_stdio.errors import AppError


def test_credential_add_writes_keyring(monkeypatch, app_config, capsys) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: app_config)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "secret")
    saved: list[tuple[str, str, str]] = []
    monkeypatch.setattr(keyring, "set_password", lambda service, alias, value: saved.append((service, alias, value)))
    assert cli.main(["cred", "add", "local"]) == 0
    assert saved == [("ft-ftp-mcp-stdio", "local", "secret")]
    assert "Credential saved" in capsys.readouterr().out


def test_credential_list_does_not_print_password(monkeypatch, app_config, capsys) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: app_config)
    monkeypatch.setattr(keyring, "get_password", lambda service, alias: "secret")
    assert cli.main(["cred", "list"]) == 0
    output = capsys.readouterr().out
    assert "local: configured" in output
    assert "secret" not in output


def test_credential_list_without_config_is_friendly(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: (_ for _ in ()).throw(AppError("invalid_config", "配置文件不存在：missing")))
    assert cli.main(["cred", "list"]) == 0
    assert "未找到配置文件" in capsys.readouterr().out


def test_unencrypted_private_key_does_not_require_stored_passphrase(monkeypatch, app_config, capsys) -> None:
    sftp = replace(app_config.servers["local"], protocol="sftp", key_path=Path("key.pem"))
    config = replace(app_config, servers={"local": sftp})
    monkeypatch.setattr(cli, "load_config", lambda: config)
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt: "")
    monkeypatch.setattr(keyring, "delete_password", lambda service, alias: None)
    assert cli.main(["cred", "add", "local"]) == 0
    assert "no passphrase stored" in capsys.readouterr().out


def test_python_module_entrypoint_handles_missing_config(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    env = {**os.environ, "FT_FTP_MCP_CONFIG": str(missing), "PYTHONUTF8": "1"}
    result = subprocess.run(
        [sys.executable, "-m", "ft_ftp_mcp_stdio", "cred", "list"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )
    assert result.returncode == 0
    assert "未找到配置文件" in result.stdout
    assert "Traceback" not in result.stderr


def test_cli_dispatches_setup_and_doctor(monkeypatch) -> None:
    monkeypatch.setattr(cli, "run_setup", lambda: 0)
    monkeypatch.setattr(cli, "run_doctor", lambda alias: 7 if alias == "sftp1" else 1)
    assert cli.main(["setup"]) == 0
    assert cli.main(["doctor", "--server", "sftp1"]) == 7


@pytest.mark.parametrize("arguments", [["-m", "foo"], ["garbage"]])
def test_server_entrypoint_rejects_unknown_arguments(monkeypatch, capsys, arguments: list[str]) -> None:
    monkeypatch.setattr(server.sys, "argv", ["ft-ftp-mcp-stdio.exe", *arguments])
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: pytest.fail("无效参数不得启动 MCP server"))

    with pytest.raises(SystemExit) as raised:
        server.main()

    assert raised.value.code == 2
    error = capsys.readouterr().err
    assert arguments[-1] in error
    assert "invalid choice" in error


def test_server_entrypoint_without_arguments_starts_stdio(monkeypatch) -> None:
    calls: list[dict[str, str]] = []
    monkeypatch.setattr(server.sys, "argv", ["ft-ftp-mcp-stdio.exe"])
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: calls.append(kwargs))

    server.main()

    assert calls == [{"transport": "stdio"}]
