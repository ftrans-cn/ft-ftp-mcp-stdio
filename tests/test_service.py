from __future__ import annotations

import os
import posixpath
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import BinaryIO

import keyring
import pytest

from ft_ftp_mcp_stdio import service as service_module
from ft_ftp_mcp_stdio.drivers.base import Entry, FileInfo
from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.service import FileService


class MemoryDriver:
    def __init__(self, files: dict[str, bytes] | None = None, dirs: set[str] | None = None) -> None:
        self.files = dict(files or {})
        self.dirs = set(dirs or {"/root"})
        self.symlinks: set[str] = set()
        self.closed = False
        self.atomic_replace = False
        self.commit_error: AppError | None = None
        self.upload_paths: list[str] = []

    def banner(self) -> str:
        return "memory"

    def list_dir(self, path: str) -> list[Entry]:
        prefix = path.rstrip("/") + "/"
        children: set[str] = set()
        for candidate in [*self.dirs, *self.files, *self.symlinks]:
            if candidate.startswith(prefix):
                relative = candidate[len(prefix):]
                if relative and "/" not in relative:
                    children.add(candidate)
        result = []
        for child in sorted(children):
            if child in self.dirs:
                result.append(Entry(posixpath.basename(child), "dir", None, None))
            elif child in self.symlinks:
                result.append(Entry(posixpath.basename(child), "symlink", None, None))
            else:
                result.append(Entry(posixpath.basename(child), "file", len(self.files[child]), "2026-09-22T00:00:00Z"))
        return result

    def get_info(self, path: str) -> FileInfo:
        if path in self.dirs:
            return FileInfo(path, "dir", None, None)
        if path in self.symlinks:
            return FileInfo(path, "symlink", None, None)
        if path in self.files:
            return FileInfo(path, "file", len(self.files[path]), "2026-09-22T00:00:00Z")
        raise AppError("not_found", "对象不存在")

    def check_path(self, path: str, root: str, *, allow_missing_final: bool = False) -> None:
        del root
        if path in self.symlinks:
            raise AppError("symlink_unsupported", "请求路径包含不受支持的符号链接")
        if not allow_missing_final:
            self.get_info(path)

    def download(self, path: str, target: BinaryIO) -> FileInfo:
        target.write(self.files[path])
        return self.get_info(path)

    def upload(self, source: BinaryIO, path: str, overwrite: bool) -> int:
        del overwrite
        self.upload_paths.append(path)
        data = bytearray()
        while chunk := source.read(2):
            data.extend(chunk)
        self.files[path] = bytes(data)
        return len(data)

    def supports_atomic_replace(self) -> bool:
        return self.atomic_replace

    def commit_upload(self, temporary_path: str, final_path: str, *, overwrite: bool) -> None:
        del overwrite
        if self.commit_error:
            raise self.commit_error
        self.files[final_path] = self.files.pop(temporary_path)

    def exists(self, path: str) -> bool:
        return path in self.files or path in self.dirs or path in self.symlinks

    def make_dir(self, path: str) -> list[str]:
        existed = path in self.dirs
        self.dirs.add(path)
        return [] if existed else [path]

    def read_prefix(self, path: str, max_bytes: int) -> bytes:
        return self.files[path][:max_bytes + 1]

    def walk(self, path: str) -> list[FileInfo]:
        prefix = path.rstrip("/") + "/"
        result = [FileInfo(item, "dir", None, None) for item in sorted(self.dirs) if item.startswith(prefix)]
        result += [FileInfo(item, "file", len(data), None) for item, data in sorted(self.files.items()) if item.startswith(prefix)]
        result += [FileInfo(item, "symlink", None, None) for item in sorted(self.symlinks) if item.startswith(prefix)]
        return result

    def move(self, from_path: str, to_path: str) -> None:
        if from_path in self.files:
            self.files[to_path] = self.files.pop(from_path)
        elif from_path in self.dirs:
            self.dirs.remove(from_path)
            self.dirs.add(to_path)
        else:
            raise AppError("not_found", "对象不存在")

    def delete_file(self, path: str) -> None:
        self.files.pop(path, None)

    def delete_dir(self, path: str) -> None:
        self.dirs.remove(path)

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(keyring, "get_password", lambda service, alias: "secret")


def service_for(app_config, driver: MemoryDriver, *, root: str = "/root") -> FileService:
    server = replace(app_config.servers["local"], root=root, read_only=False)
    config = replace(app_config, servers={"local": server})
    return FileService(config, lambda candidate, password: driver)


def test_list_servers_and_virtual_path_minimize_sensitive_fields(app_config) -> None:
    server = replace(app_config.servers["local"], root="/secret/root", description="财务报表")
    config = replace(app_config, servers={"local": server})
    result = FileService(config).list_servers()
    assert result == {"ok": True, "servers": [{"alias": "local", "description": "财务报表", "protocol": "ftp", "read_only": False, "is_default": True}]}


def test_virtual_paths_map_to_driver_and_back(app_config) -> None:
    driver = MemoryDriver({"/root/reports/a.csv": b"x"}, {"/root", "/root/reports"})
    service = service_for(app_config, driver)
    listed = service.list_dir("/reports")
    assert listed["path"] == "/reports"
    assert listed["entries"] == [{"name": "a.csv", "type": "file", "size": 1, "mtime": "2026-09-22T00:00:00Z"}]
    assert service.get_file_info("/reports/a.csv")["path"] == "/reports/a.csv"


def test_read_only_rejects_before_credentials_or_connection(monkeypatch: pytest.MonkeyPatch, app_config, tmp_path: Path) -> None:
    local = tmp_path / "a.txt"
    local.write_text("a", encoding="utf-8")
    server = replace(app_config.servers["local"], root="/root", read_only=True)
    config = replace(app_config, servers={"local": server})
    monkeypatch.setattr(keyring, "get_password", lambda *args: pytest.fail("credential read"))
    with pytest.raises(AppError) as raised:
        FileService(config, lambda *_: pytest.fail("connected")).upload_file(str(local), "/a.txt")
    assert raised.value.error_type == "policy_rejected"


def test_upload_uses_random_temporary_object_then_commits(app_config, tmp_path: Path) -> None:
    local = tmp_path / "a.txt"
    local.write_bytes(b"data")
    driver = MemoryDriver()
    result = service_for(app_config, driver).upload_file(str(local), "/a.txt")
    assert result == {"ok": True, "remote_path": "/a.txt", "size": 4, "status": "completed"}
    assert driver.files["/root/a.txt"] == b"data"
    assert len(driver.upload_paths) == 1
    assert posixpath.basename(driver.upload_paths[0]).startswith(".a.txt.ft-upload-")
    assert posixpath.basename(driver.upload_paths[0]).endswith(".tmp")


def test_upload_limit_precheck_and_streaming_cleanup(app_config, tmp_path: Path) -> None:
    local = tmp_path / "large.bin"
    local.write_bytes(b"12345")
    driver = MemoryDriver()
    server = replace(app_config.servers["local"], root="/root", read_only=False, max_file_size_bytes=4)
    config = replace(app_config, servers={"local": server})
    with pytest.raises(AppError) as raised:
        FileService(config, lambda *_: pytest.fail("must not connect")).upload_file(str(local), "/large.bin")
    assert raised.value.error_type == "size_limit_exceeded"
    assert raised.value.details == {"limit_kind": "upload_file_bytes", "configured_limit": 4, "observed_value": 5, "observation": "exact", "remote_committed": False}
    assert driver.files == {}


def test_overwrite_requires_atomic_replace_capability(app_config, tmp_path: Path) -> None:
    local = tmp_path / "a.txt"
    local.write_bytes(b"new")
    driver = MemoryDriver({"/root/a.txt": b"old"})
    with pytest.raises(AppError) as raised:
        service_for(app_config, driver).upload_file(str(local), "/a.txt", overwrite=True)
    assert raised.value.error_type == "policy_rejected"
    assert driver.files["/root/a.txt"] == b"old"


def test_commit_response_loss_is_outcome_unknown_and_not_replayed(app_config, tmp_path: Path) -> None:
    local = tmp_path / "a.txt"
    local.write_bytes(b"data")
    driver = MemoryDriver()
    driver.commit_error = AppError("connection_unavailable", "lost")
    with pytest.raises(AppError) as raised:
        service_for(app_config, driver).upload_file(str(local), "/a.txt")
    assert raised.value.error_type == "outcome_unknown"
    assert raised.value.details is not None
    assert raised.value.details["operation"] == "upload_file"
    assert len(driver.upload_paths) == 1


def test_download_integrity_mismatch_removes_staging(app_config) -> None:
    class MismatchDriver(MemoryDriver):
        def get_info(self, path: str) -> FileInfo:
            info = super().get_info(path)
            return replace(info, size=99)
    driver = MismatchDriver({"/root/a.txt": b"data"})
    service = service_for(app_config, driver)
    with pytest.raises(AppError) as raised:
        service.download_file("/a.txt")
    assert raised.value.error_type == "integrity_check_failed"
    assert not service.config.staging_dir.exists() or not any(service.config.staging_dir.iterdir())


def test_download_retry_cleans_partial_file_before_second_attempt(app_config) -> None:
    calls = 0

    class RetryDriver(MemoryDriver):
        def download(self, path: str, target: BinaryIO) -> FileInfo:
            nonlocal calls
            calls += 1
            if calls == 1:
                target.write(b"partial")
                raise AppError("connection_unavailable", "connection lost")
            return super().download(path, target)

    service = service_for(app_config, RetryDriver({"/root/a.txt": b"ok"}))
    result = service.download_file("/a.txt")
    assert calls == 2
    assert Path(str(result["local_path"])).read_bytes() == b"ok"


@pytest.mark.parametrize(("raw", "encoding"), [(b"a\n", "utf-8"), (b"\xef\xbb\xbfa\n", "utf-8-sig"), ("中文\n".encode("gbk"), "gbk")])
def test_preview_reports_encoding_and_partial_line(app_config, raw: bytes, encoding: str) -> None:
    result = service_for(app_config, MemoryDriver({"/root/a.txt": raw})).read_text_preview("/a.txt", max_bytes=max(1, len(raw) - 1))
    assert result["encoding"] == encoding
    assert result["truncated"] is True
    assert result["total_lines"] is None


def test_virtual_root_mutations_are_rejected(app_config) -> None:
    service = service_for(app_config, MemoryDriver())
    for call in (lambda: service.delete("/", True), lambda: service.rename("/", "x"), lambda: service.move("/", "/x"), lambda: service.move("/x", "/")):
        with pytest.raises(AppError) as raised:
            call()
        assert raised.value.error_type == "policy_rejected"


def test_batch_results_use_stable_paths_and_status(app_config, tmp_path: Path) -> None:
    driver = MemoryDriver({"/root/tree/a.txt": b"a"}, {"/root", "/root/tree"})
    driver.symlinks.add("/root/tree/link")
    download = service_for(app_config, driver).download_dir("/tree")
    assert download["status"] == "partial"
    assert download["skipped"] == [{"path": "/tree/link", "reason_type": "symlink_unsupported", "message": "符号链接不受支持"}]
    source = tmp_path / "source"
    source.mkdir()
    (source / "b.txt").write_bytes(b"b")
    upload = service_for(app_config, driver).upload_dir(str(source), "/uploaded")
    assert upload["status"] == "complete"
    assert upload["indeterminate"] == []
    assert upload["file_count"] == 1


def test_upload_dir_records_uncertain_subdirectory_creation_as_indeterminate(app_config, tmp_path: Path) -> None:
    class UncertainDirectoryDriver(MemoryDriver):
        def make_dir(self, path: str) -> list[str]:
            if path.endswith("/nested"):
                raise AppError("connection_unavailable", "response lost")
            return super().make_dir(path)

    source = tmp_path / "source"
    (source / "nested").mkdir(parents=True)
    result = service_for(app_config, UncertainDirectoryDriver()).upload_dir(str(source), "/uploaded")
    assert result["status"] == "indeterminate"
    assert result["failed"] == []
    assert result["indeterminate"] == [
        {
            "path": "nested",
            "error_type": "outcome_unknown",
            "message": "远端写操作的结果无法确认，请人工核验后再决定是否重试",
            "evidence": [{"kind": "post_state", "result": "unavailable", "path": "nested"}],
        }
    ]


def test_download_dir_records_malicious_entry_without_echoing_name(app_config) -> None:
    class MaliciousDriver(MemoryDriver):
        def list_dir(self, path: str) -> list[Entry]:
            if path == "/root/tree":
                return [Entry("../escape", "file", 1, None), Entry("ok.txt", "file", 2, None)]
            return super().list_dir(path)

    driver = MaliciousDriver({"/root/tree/ok.txt": b"ok"}, {"/root", "/root/tree"})
    result = service_for(app_config, driver).download_dir("/tree")
    assert result["file_count"] == 1
    assert result["failed"] == [{"path": "/tree", "error_type": "invalid_path", "message": "服务器返回了非法目录项名称"}]
    assert "escape" not in result["failed"][0]["path"]


def test_generated_errors_do_not_leak_connection_metadata(app_config) -> None:
    secret_values = ["10.0.0.7", "2121", "private-user", "/real/root", "id_ed25519", "SHA256:secret", "PASSWORD_ENV"]
    server = replace(
        app_config.servers["local"],
        host=secret_values[0],
        port=2121,
        username=secret_values[2],
        root=secret_values[3],
        credential_env=secret_values[6],
    )
    config = replace(app_config, servers={"local": server})
    service = FileService(config, lambda *_: (_ for _ in ()).throw(RuntimeError("/real/root SHA256:secret")))
    with pytest.raises(AppError) as raised:
        service.list_dir("/")
    rendered = str(raised.value.as_result())
    for secret in secret_values:
        assert secret not in rendered


def test_local_symlink_is_rejected_without_reading(app_config, tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError as exc:
        if os.name == "nt" and exc.winerror == 1314:
            pytest.skip("Windows symlink privilege unavailable (WinError 1314)")
        raise
    with pytest.raises(AppError) as raised:
        service_for(app_config, MemoryDriver()).upload_file(str(link), "/link.txt")
    assert raised.value.error_type == "symlink_unsupported"


def test_local_filesystem_root_is_accepted_as_directory() -> None:
    root = Path(Path.cwd().anchor)

    assert service_module._validate_local_directory(root) == root


def test_local_root_type_is_checked(monkeypatch, tmp_path: Path) -> None:
    root = Path(Path.cwd().anchor)
    regular_file = tmp_path / "source.txt"
    regular_file.write_text("content", encoding="utf-8")
    file_info = regular_file.lstat()
    monkeypatch.setattr(Path, "lstat", lambda path: file_info)

    with pytest.raises(AppError) as raised:
        service_module._validate_local_directory(root)

    assert raised.value.error_type == "not_found"


def test_missing_local_root_is_rejected_before_connection(monkeypatch, app_config) -> None:
    root = Path(Path.cwd().anchor)

    def missing_root(path: Path):
        raise FileNotFoundError(path)

    monkeypatch.setattr(Path, "lstat", missing_root)
    service = FileService(app_config, lambda *_: pytest.fail("must not connect"))

    with pytest.raises(AppError) as raised:
        service.upload_dir(str(root), "/root")

    assert raised.value.error_type == "not_found"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows junction test")
def test_local_windows_junction_is_rejected(app_config, tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "secret.txt").write_text("secret", encoding="utf-8")
    junction = tmp_path / "junction"
    created = subprocess.run(
        ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stderr or created.stdout
    moved = tmp_path / "moved-target"
    try:
        with pytest.raises(AppError) as raised:
            service_for(app_config, MemoryDriver()).upload_dir(str(junction), "/junction")
        assert raised.value.error_type == "symlink_unsupported"
        with pytest.raises(AppError) as parent_link:
            service_for(app_config, MemoryDriver()).upload_file(str(junction / "secret.txt"), "/secret.txt")
        assert parent_link.value.error_type == "symlink_unsupported"
        target.rename(moved)
        with pytest.raises(AppError) as broken:
            service_for(app_config, MemoryDriver()).upload_dir(str(junction), "/broken")
        assert broken.value.error_type == "symlink_unsupported"
    finally:
        junction.rmdir()
    assert (moved / "secret.txt").read_text(encoding="utf-8") == "secret"


def test_local_reparse_attribute_is_rejected_before_connection(monkeypatch, app_config, tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("secret", encoding="utf-8")
    original_lstat = Path.lstat

    def marked_lstat(path: Path):
        info = original_lstat(path)
        if path == source:
            return type("ReparseStat", (), {"st_mode": info.st_mode, "st_file_attributes": 0x400})()
        return info

    monkeypatch.setattr(Path, "lstat", marked_lstat)
    with pytest.raises(AppError) as raised:
        FileService(app_config, lambda *_: pytest.fail("must not connect")).upload_file(str(source), "/source.txt", alias="local")
    assert raised.value.error_type == "symlink_unsupported"


def test_local_handle_identity_mismatch_is_rejected_before_read(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("secret", encoding="utf-8")
    before = source.stat()
    monkeypatch.setattr(service_module, "_assert_plain_path", lambda path: before)
    monkeypatch.setattr(service_module.os, "fstat", lambda fd: os.stat_result((before.st_mode, before.st_ino + 1, before.st_dev, 1, 0, 0, 0, 0, 0, 0)))
    with pytest.raises(AppError) as raised, service_module._open_verified_local(source):
        pytest.fail("file body became readable")
    assert raised.value.error_type == "symlink_unsupported"
