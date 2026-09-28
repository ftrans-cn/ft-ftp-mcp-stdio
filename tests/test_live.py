from __future__ import annotations

import hashlib
from pathlib import Path
from typing import cast

import keyring
import pytest

from ft_ftp_mcp_stdio.config import load_config
from ft_ftp_mcp_stdio.credentials import SERVICE_NAME
from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.service import FileService

LIVE_ROOTS = {
    "ftp1": "/mcp_ftp_next_development_20260922",
    "sftp1": "/mcp_sftp_next_development_20260922",
}


@pytest.mark.live
@pytest.mark.parametrize(
    ("alias", "remote_dir"),
    list(LIVE_ROOTS.items()),
)
def test_all_poc_tools_against_serv_u(alias: str, remote_dir: str, tmp_path: Path) -> None:
    config = load_config()
    if alias not in config.servers:
        pytest.fail(f"live 配置缺少服务器别名: {alias}")
    service = FileService(config)
    source = tmp_path / f"{alias}-first-batch.txt"
    source.write_text(f"first batch live check: {alias}\n", encoding="utf-8")
    remote_file = f"{remote_dir}/first-batch-live.txt"
    _delete_tree(service, remote_dir, alias)
    try:
        assert service.test_connection(alias)["ok"] is True
        assert service.make_dir(remote_dir, alias)["ok"] is True
        upload = service.upload_file(str(source), remote_file, alias=alias)
        assert upload["size"] == source.stat().st_size
        assert service.get_file_info(remote_file, alias)["type"] == "file"
        entries = cast(list[dict[str, object]], service.list_dir(remote_dir, alias)["entries"])
        matches = cast(list[dict[str, object]], service.search_files(remote_dir, "first-batch-live.txt", alias)["matches"])
        assert any(entry["name"] == "first-batch-live.txt" for entry in entries)
        assert any(match["path"] == remote_file for match in matches)
        download = service.download_file(remote_file, alias)
        assert download["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    finally:
        _delete_tree(service, remote_dir, alias)


@pytest.mark.live
def test_ftp_root_listing_against_serv_u() -> None:
    service = FileService(load_config())
    result = service.list_dir("/", "ftp1")
    assert result["ok"] is True
    assert isinstance(result["entries"], list)


@pytest.mark.live
@pytest.mark.parametrize("alias", ["ftp1", "sftp1"])
def test_live_parent_path_segments_are_rejected_locally(alias: str) -> None:
    service = FileService(load_config())
    with pytest.raises(AppError) as exc_info:
        service.list_dir("/../", alias)
    assert exc_info.value.error_type == "invalid_path"


def _delete_tree(service: FileService, path: str, alias: str) -> None:
    try:
        entries = cast(list[dict[str, object]], service.list_dir(path, alias)["entries"])
    except AppError:
        return
    for entry in entries:
        child = f"{path.rstrip('/')}/{entry['name']}"
        if entry["type"] == "dir":
            _delete_tree(service, child, alias)
        else:
            service.delete(child, True, alias)
    service.delete(path, True, alias)


@pytest.mark.live
@pytest.mark.parametrize("alias", ["ftp1", "sftp1"])
def test_all_mvp_tools_against_serv_u(alias: str, tmp_path: Path) -> None:
    service = FileService(load_config())
    root = LIVE_ROOTS[alias]
    _delete_tree(service, root, alias)
    try:
        service.make_dir(f"{root}/dest", alias)
        service.make_dir(f"{root}/empty", alias)
        source = tmp_path / "source.txt"
        source.write_text("标题\n第一行\n第二行\n", encoding="utf-8", newline="\n")
        remote = f"{root}/source.txt"
        service.upload_file(str(source), remote, alias=alias)

        preview = service.read_text_preview(remote, max_bytes=1024, alias=alias)
        assert preview["content"] == source.read_text(encoding="utf-8")
        gbk_source = tmp_path / "gbk.csv"
        gbk_text = "列一,列二\n一,二\n三,四\n"
        gbk_source.write_bytes(gbk_text.encode("gbk"))
        gbk_remote = f"{root}/gbk.csv"
        service.upload_file(str(gbk_source), gbk_remote, alias=alias)
        first_line_bytes = len("列一,列二\n一".encode("gbk"))
        gbk_preview = service.read_text_preview(gbk_remote, max_bytes=first_line_bytes, alias=alias)
        assert gbk_preview["content"] == "列一,列二\n一"
        assert gbk_preview["partial_line"] is True
        assert gbk_preview["truncated"] is True
        assert gbk_preview["total_lines"] is None
        renamed = service.rename(remote, "renamed.txt", alias)
        assert renamed["new_path"] == f"{root}/renamed.txt"
        moved = service.move(f"{root}/renamed.txt", f"{root}/dest/moved.txt", alias)
        assert moved["to_path"] == f"{root}/dest/moved.txt"

        local_tree = tmp_path / f"upload-{alias}"
        (local_tree / "nested" / "empty").mkdir(parents=True)
        (local_tree / "one.txt").write_text("one", encoding="utf-8")
        (local_tree / "nested" / "two.txt").write_text("two", encoding="utf-8")
        uploaded = service.upload_dir(str(local_tree), f"{root}/uploaded", alias=alias)
        assert uploaded["file_count"] == 2
        assert uploaded["failed"] == []

        downloaded = service.download_dir(f"{root}/uploaded", alias=alias)
        downloaded_root = Path(str(downloaded["local_dir"]))
        assert downloaded["file_count"] == 2
        assert (downloaded_root / "nested" / "empty").is_dir()
        assert (downloaded_root / "nested" / "two.txt").read_text(encoding="utf-8") == "two"

        assert service.delete(f"{root}/dest/moved.txt", True, alias)["type"] == "file"
        assert service.delete(f"{root}/empty", True, alias)["type"] == "dir"
    finally:
        _delete_tree(service, root, alias)


@pytest.mark.live
def test_sftp_unencrypted_private_key_login_without_credential() -> None:
    config = load_config()
    alias = "sftp-key-nopass-v2"
    assert alias in config.servers
    key_path = config.servers[alias].key_path
    assert key_path is not None
    assert key_path.is_file()
    assert keyring.get_password(SERVICE_NAME, alias) is None
    result = FileService(config).test_connection(alias)
    assert result["ok"] is True
    assert result == {"ok": True, "server": alias, "protocol": "sftp", "read_only": config.servers[alias].read_only}


@pytest.mark.live
def test_sftp_encrypted_private_key_login_from_keyring() -> None:
    config = load_config()
    alias = "sftp-key-pass-v2"
    assert alias in config.servers
    key_path = config.servers[alias].key_path
    assert key_path is not None
    assert key_path.is_file()
    assert keyring.get_password(SERVICE_NAME, alias)
    result = FileService(config).test_connection(alias)
    assert result["ok"] is True
    assert result == {"ok": True, "server": alias, "protocol": "sftp", "read_only": config.servers[alias].read_only}


@pytest.mark.live
def test_sftp_password_login_remains_available() -> None:
    config = load_config()
    assert config.servers["sftp1"].key_path is None
    result = FileService(config).test_connection("sftp1")
    assert result["ok"] is True
    assert result == {"ok": True, "server": "sftp1", "protocol": "sftp", "read_only": config.servers["sftp1"].read_only}
