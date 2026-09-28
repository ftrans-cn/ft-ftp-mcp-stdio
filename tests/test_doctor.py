from __future__ import annotations

import json
from pathlib import Path

import keyring

from ft_ftp_mcp_stdio import doctor
from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.service import FileService


def test_doctor_keeps_running_when_config_is_invalid(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{broken", encoding="utf-8")
    monkeypatch.setenv("FT_FTP_MCP_CONFIG", str(path))
    checks = doctor.diagnose()
    assert checks[0].name == "运行环境"
    assert any(check.name == "使用日志目录" for check in checks)
    assert any(check.status == "FAIL" and check.name == "配置文件" for check in checks)
    assert any(check.status == "SKIP" for check in checks)


def test_doctor_runs_independent_checks_and_does_not_write_known_hosts(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                    "version": 2,
                "default_server": "sftp",
                    "servers": [{"alias": "sftp", "protocol": "sftp", "host": "127.0.0.1", "username": "u", "root": "/"}],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("FT_FTP_MCP_CONFIG", str(path))
    monkeypatch.setattr(keyring, "get_password", lambda service, alias: "secret")
    monkeypatch.setattr(doctor.socket, "create_connection", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("offline")))
    monkeypatch.setattr(FileService, "test_connection", lambda self, alias: (_ for _ in ()).throw(AppError("credential_missing", "bad login")))

    checks = doctor.diagnose("sftp")
    assert any(check.name.endswith("/TCP") and check.status == "FAIL" for check in checks)
    assert any(check.name.endswith("/协议登录") and check.status == "FAIL" for check in checks)
    assert any(check.name.endswith("/SFTP指纹") and check.status == "WARN" for check in checks)
    assert not (tmp_path / "known_hosts").exists()


def test_doctor_exit_code_is_nonzero_only_for_fail(monkeypatch) -> None:
    monkeypatch.setattr(doctor, "diagnose", lambda alias: [doctor.Check("WARN", "x", "warning")])
    assert doctor.run_doctor() == 0
    monkeypatch.setattr(doctor, "diagnose", lambda alias: [doctor.Check("FAIL", "x", "failure")])
    assert doctor.run_doctor() == 1


def test_doctor_checks_usage_log_directory_without_creating_it(monkeypatch, tmp_path: Path) -> None:
    directory = tmp_path / "missing" / "logs"
    monkeypatch.setattr(doctor, "usage_log_dir", lambda: directory)
    check = doctor._log_directory_check()
    assert check.status == "PASS"
    assert not directory.exists()


def test_runtime_check_only_accepts_python_312(monkeypatch) -> None:
    monkeypatch.setattr(doctor.sys, "version_info", (3, 12, 0))
    assert doctor._runtime_check().status == "PASS"

    monkeypatch.setattr(doctor.sys, "version_info", (3, 11, 9))
    lower = doctor._runtime_check()
    assert lower.status == "FAIL"
    assert lower.suggestion == "仅支持 Python 3.12.x"

    monkeypatch.setattr(doctor.sys, "version_info", (3, 13, 0))
    assert doctor._runtime_check().status == "FAIL"
