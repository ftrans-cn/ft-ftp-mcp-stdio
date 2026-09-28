from __future__ import annotations

import hashlib
import os
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import jsonschema  # type: ignore[import-untyped]
import keyring
import paramiko
import pytest
from test_service import MemoryDriver, service_for

from ft_ftp_mcp_stdio.contracts import ERROR_TYPES, OUTPUT_SCHEMAS
from ft_ftp_mcp_stdio.drivers.base import FileInfo
from ft_ftp_mcp_stdio.drivers.ftp import _mlsd_time
from ft_ftp_mcp_stdio.drivers.sftp import SFTPDriver, _mtime
from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.known_hosts import KnownHostsStore
from ft_ftp_mcp_stdio.service import FileService


@pytest.fixture(autouse=True)
def credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(keyring, "get_password", lambda service, alias: "secret")


def test_every_error_variant_validates_against_public_schema() -> None:
    schema = OUTPUT_SCHEMAS["list_servers"]
    for error_type in ERROR_TYPES:
        details = None
        if error_type == "size_limit_exceeded":
            details = {"limit_kind": "upload_file_bytes", "configured_limit": 1, "observed_value": 2, "observation": "exact", "remote_committed": False}
        elif error_type == "outcome_unknown":
            details = {"operation": "delete", "phase": "response_wait", "paths": ["/x"], "evidence": []}
        jsonschema.validate(AppError(error_type, "safe", details=details).as_result(), schema)  # type: ignore[arg-type]


def test_runtime_parameter_errors_are_stable(app_config) -> None:
    service = service_for(app_config, MemoryDriver({"/root/a.txt": b"a"}))
    with pytest.raises(AppError) as pattern:
        service.search_files("/", "")
    assert pattern.value.error_type == "invalid_argument"
    with pytest.raises(AppError) as preview:
        service.read_text_preview("/a.txt", 1048577)
    assert preview.value.error_type == "policy_rejected"
    with pytest.raises(AppError) as confirm:
        service.delete("/a.txt", False)
    assert confirm.value.error_type == "policy_rejected"


def test_upload_dir_stream_limit_skips_item_and_continues(app_config, tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "large.bin").write_bytes(b"12345")
    (source / "small.bin").write_bytes(b"12")
    server = replace(app_config.servers["local"], root="/root", read_only=False, max_file_size_bytes=3)
    config = replace(app_config, servers={"local": server})
    result = FileService(config, lambda *_: MemoryDriver()).upload_dir(str(source), "/target")
    assert result["status"] == "partial"
    assert result["file_count"] == 1
    skipped = cast(list[dict[str, Any]], result["skipped"])
    assert skipped[0]["path"] == "large.bin"
    assert skipped[0]["details"]["observation"] == "at_least"


def test_zero_upload_limit_allows_file(app_config, tmp_path: Path) -> None:
    source = tmp_path / "data.bin"
    source.write_bytes(b"123456")
    server = replace(app_config.servers["local"], root="/root", read_only=False, max_file_size_bytes=0)
    config = replace(app_config, servers={"local": server})
    assert FileService(config, lambda *_: MemoryDriver()).upload_file(str(source), "/data.bin")["size"] == 6


def test_three_temporary_name_collisions_fail_without_upload(monkeypatch: pytest.MonkeyPatch, app_config, tmp_path: Path) -> None:
    source = tmp_path / "a.txt"
    source.write_bytes(b"a")
    temporary = "/root/.a.txt.ft-upload-0000000000000000.tmp"
    driver = MemoryDriver({temporary: b"other"})
    monkeypatch.setattr("ft_ftp_mcp_stdio.service.secrets.token_hex", lambda size: "0" * 16)
    with pytest.raises(AppError) as raised:
        service_for(app_config, driver).upload_file(str(source), "/a.txt")
    assert raised.value.error_type == "server_error"
    assert driver.upload_paths == []


def test_temporary_name_check_failure_does_not_start_upload(app_config, tmp_path: Path) -> None:
    class UnknownTemporaryState(MemoryDriver):
        def exists(self, path: str) -> bool:
            if ".ft-upload-" in path:
                raise AppError("permission_denied", "cannot inspect")
            return super().exists(path)

    source = tmp_path / "a.txt"
    source.write_bytes(b"a")
    driver = UnknownTemporaryState()
    with pytest.raises(AppError) as raised:
        service_for(app_config, driver).upload_file(str(source), "/a.txt")
    assert raised.value.error_type == "permission_denied"
    assert driver.upload_paths == []


def test_temporary_cleanup_check_failure_reports_possible_residue(app_config, tmp_path: Path) -> None:
    class CleanupUnknown(MemoryDriver):
        def upload(self, source, path: str, overwrite: bool) -> int:
            super().upload(source, path, overwrite)
            raise AppError("connection_unavailable", "lost")

        def exists(self, path: str) -> bool:
            if ".ft-upload-" in path and path in self.files:
                raise AppError("permission_denied", "cannot inspect")
            return super().exists(path)

    source = tmp_path / "a.txt"
    source.write_bytes(b"a")
    driver = CleanupUnknown()
    with pytest.raises(AppError) as raised:
        service_for(app_config, driver).upload_file(str(source), "/a.txt")
    assert raised.value.error_type == "server_error"
    assert any(".ft-upload-" in path for path in driver.files)


@pytest.mark.parametrize("operation", ["upload_file", "upload_dir", "make_dir", "rename", "move", "delete"])
def test_connection_failure_before_write_dispatch_is_retried_once(app_config, tmp_path: Path, operation: str) -> None:
    calls = 0
    driver = MemoryDriver({"/root/a.txt": b"a"})
    source = tmp_path / "source.txt"
    source.write_bytes(b"source")
    source_dir = tmp_path / "source-dir"
    source_dir.mkdir()
    server = replace(app_config.servers["local"], root="/root", read_only=False)
    config = replace(app_config, servers={"local": server})

    def factory(*args):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise AppError("connection_unavailable", "offline")
        return driver

    service = FileService(config, factory)
    result = {
        "upload_file": lambda: service.upload_file(str(source), "/uploaded.txt"),
        "upload_dir": lambda: service.upload_dir(str(source_dir), "/uploaded-dir"),
        "make_dir": lambda: service.make_dir("/new"),
        "rename": lambda: service.rename("/a.txt", "renamed.txt"),
        "move": lambda: service.move("/a.txt", "/moved.txt"),
        "delete": lambda: service.delete("/a.txt", True),
    }[operation]()
    assert result["status"] == ("complete" if operation == "upload_dir" else "completed")
    assert calls == 2


def test_make_dir_response_loss_recovers_from_matching_post_state(app_config) -> None:
    calls = 0

    class CompletedThenLost(MemoryDriver):
        def make_dir(self, path: str) -> list[str]:
            nonlocal calls
            calls += 1
            super().make_dir(path)
            raise AppError("connection_unavailable", "lost")

    driver = CompletedThenLost()
    result = service_for(app_config, driver).make_dir("/new")
    assert result == {"ok": True, "path": "/new", "created": True, "status": "completed"}
    assert calls == 1


def test_make_dir_response_loss_retries_once_when_post_state_is_absent(app_config) -> None:
    calls = 0

    class LostBeforeChange(MemoryDriver):
        def make_dir(self, path: str) -> list[str]:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise AppError("connection_unavailable", "lost")
            return super().make_dir(path)

    driver = LostBeforeChange()
    result = service_for(app_config, driver).make_dir("/new")
    assert result["status"] == "completed"
    assert calls == 2


def test_move_response_loss_requires_stable_identity_for_success(app_config) -> None:
    class UniqueMove(MemoryDriver):
        def __init__(self) -> None:
            super().__init__({"/root/a.txt": b"a"})
            self.identities = {"/root/a.txt": "unique-1"}

        def identity(self, path: str) -> str | None:
            return self.identities.get(path)

        def move(self, from_path: str, to_path: str) -> None:
            super().move(from_path, to_path)
            self.identities[to_path] = self.identities.pop(from_path)
            raise AppError("connection_unavailable", "lost")

    result = service_for(app_config, UniqueMove()).move("/a.txt", "/b.txt")
    assert result["status"] == "completed"


def test_move_recovery_refreshes_identity_on_new_driver(app_config) -> None:
    shared_files = {"/root/a.txt": b"a"}
    created = 0

    class CachedIdentityDriver(MemoryDriver):
        def __init__(self, lose_response: bool) -> None:
            super().__init__()
            self.files = shared_files
            self.lose_response = lose_response
            self.loaded: set[str] = set()

        def get_info(self, path: str) -> FileInfo:
            info = super().get_info(path)
            self.loaded.add(path)
            return info

        def identity(self, path: str) -> str | None:
            return "unique-1" if path in self.loaded else None

        def move(self, from_path: str, to_path: str) -> None:
            super().move(from_path, to_path)
            if self.lose_response:
                raise AppError("connection_unavailable", "lost")

    def factory(*args):
        nonlocal created
        created += 1
        return CachedIdentityDriver(lose_response=created == 1)

    server = replace(app_config.servers["local"], protocol="ftp", root="/root", read_only=False)
    config = replace(app_config, servers={"local": server})
    result = FileService(config, factory).move("/a.txt", "/b.txt")
    assert result["status"] == "completed"
    assert created == 2


def test_move_response_loss_rejects_concurrent_target_replacement(app_config) -> None:
    class ReplacedTarget(MemoryDriver):
        def __init__(self) -> None:
            super().__init__({"/root/a.txt": b"a"})
            self.identities = {"/root/a.txt": "source-identity"}

        def identity(self, path: str) -> str | None:
            return self.identities.get(path)

        def move(self, from_path: str, to_path: str) -> None:
            self.files.pop(from_path)
            self.files[to_path] = b"replacement"
            self.identities.pop(from_path)
            self.identities[to_path] = "replacement-identity"
            raise AppError("connection_unavailable", "lost")

    with pytest.raises(AppError) as raised:
        service_for(app_config, ReplacedTarget()).move("/a.txt", "/b.txt")
    assert raised.value.error_type == "outcome_unknown"
    assert raised.value.details is not None
    assert raised.value.details["evidence"][0]["result"] == "mismatched"


@pytest.mark.parametrize("protocol", ["sftp", "ftp"])
def test_move_response_loss_without_stable_identity_is_unknown(app_config, protocol: str) -> None:
    class NoIdentityMove(MemoryDriver):
        def move(self, from_path: str, to_path: str) -> None:
            super().move(from_path, to_path)
            raise AppError("connection_unavailable", "lost")

    driver = NoIdentityMove({"/root/a.txt": b"a"})
    server = replace(app_config.servers["local"], protocol=protocol, root="/root", read_only=False)
    config = replace(app_config, servers={"local": server})
    with pytest.raises(AppError) as raised:
        FileService(config, lambda *_: driver).move("/a.txt", "/b.txt")
    assert raised.value.error_type == "outcome_unknown"


def test_upload_commit_loss_recovers_only_with_matching_remote_hash(app_config, tmp_path: Path) -> None:
    class HashingDriver(MemoryDriver):
        def commit_upload(self, temporary_path: str, final_path: str, *, overwrite: bool) -> None:
            super().commit_upload(temporary_path, final_path, overwrite=overwrite)
            raise AppError("connection_unavailable", "lost")

        def content_hash(self, path: str) -> str | None:
            data = self.files.get(path)
            return hashlib.sha256(data).hexdigest() if data is not None else None

    source = tmp_path / "a.txt"
    source.write_bytes(b"content")
    result = service_for(app_config, HashingDriver()).upload_file(str(source), "/a.txt")
    assert result["status"] == "completed"


def test_upload_commit_loss_rejects_mismatched_remote_hash(app_config, tmp_path: Path) -> None:
    class MismatchedHash(MemoryDriver):
        def commit_upload(self, temporary_path: str, final_path: str, *, overwrite: bool) -> None:
            super().commit_upload(temporary_path, final_path, overwrite=overwrite)
            raise AppError("connection_unavailable", "lost")

        def content_hash(self, path: str) -> str | None:
            return "not-the-uploaded-content"

    source = tmp_path / "a.txt"
    source.write_bytes(b"content")
    with pytest.raises(AppError) as raised:
        service_for(app_config, MismatchedHash()).upload_file(str(source), "/a.txt")
    assert raised.value.error_type == "outcome_unknown"
    assert raised.value.details is not None
    assert raised.value.details["evidence"][0]["result"] == "mismatched"


@pytest.mark.parametrize("operation", ["rename", "move", "delete"])
def test_write_response_loss_is_not_replayed(app_config, operation: str) -> None:
    calls = 0

    class Interrupted(MemoryDriver):
        def make_dir(self, path: str) -> list[str]:
            nonlocal calls
            calls += 1
            raise AppError("connection_unavailable", "lost")
        def move(self, from_path: str, to_path: str) -> None:
            nonlocal calls
            calls += 1
            raise AppError("connection_unavailable", "lost")
        def delete_file(self, path: str) -> None:
            nonlocal calls
            calls += 1
            raise AppError("connection_unavailable", "lost")

    driver = Interrupted({"/root/a.txt": b"a"})
    service = service_for(app_config, driver)
    call = {
        "make_dir": lambda: service.make_dir("/new"),
        "rename": lambda: service.rename("/a.txt", "b.txt"),
        "move": lambda: service.move("/a.txt", "/b.txt"),
        "delete": lambda: service.delete("/a.txt", True),
    }[operation]
    with pytest.raises(AppError) as raised:
        call()
    assert raised.value.error_type == "outcome_unknown"
    assert calls == 1


def test_sftp_not_found_does_not_retry(app_config) -> None:
    attempts = 0

    class Missing(MemoryDriver):
        def get_info(self, path: str) -> FileInfo:
            raise AppError("not_found", "missing")

    def factory(*args):
        nonlocal attempts
        attempts += 1
        return Missing()

    server = replace(app_config.servers["local"], protocol="sftp", root="/root")
    config = replace(app_config, servers={"local": server})
    with pytest.raises(AppError) as raised:
        FileService(config, factory).get_file_info("/missing")
    assert raised.value.error_type == "not_found"
    assert attempts == 1


def test_sftp_segment_lstat_rejects_root_and_path_links() -> None:
    class Attr:
        def __init__(self, mode: int) -> None:
            self.st_mode = mode

    class Channel:
        def __init__(self, link: str) -> None:
            self.link = link
        def lstat(self, path: str) -> Attr:
            import stat
            return Attr(stat.S_IFLNK if path == self.link else stat.S_IFDIR)

    driver = object.__new__(SFTPDriver)
    driver._sftp = cast(paramiko.SFTPClient, Channel("/srv"))
    with pytest.raises(AppError) as root_link:
        driver.check_path("/srv/root/a", "/srv/root")
    assert root_link.value.error_type == "invalid_config"
    driver._sftp = cast(paramiko.SFTPClient, Channel("/srv/root/a"))
    with pytest.raises(AppError) as path_link:
        driver.check_path("/srv/root/a", "/srv/root")
    assert path_link.value.error_type == "symlink_unsupported"


@pytest.mark.parametrize("operation", ["make_dir", "upload_dir"])
def test_create_operations_check_remote_parent_links_before_writing(app_config, tmp_path: Path, operation: str) -> None:
    writes = 0

    class LinkedParent(MemoryDriver):
        def check_path(self, path: str, root: str, *, allow_missing_final: bool = False) -> None:
            del root, allow_missing_final
            if path.startswith("/root/link/"):
                raise AppError("symlink_unsupported", "linked parent")

        def make_dir(self, path: str) -> list[str]:
            nonlocal writes
            writes += 1
            return super().make_dir(path)

    source = tmp_path / "source"
    source.mkdir()
    service = service_for(app_config, LinkedParent())
    call = (
        (lambda: service.make_dir("/link/new"))
        if operation == "make_dir"
        else (lambda: service.upload_dir(str(source), "/link/new"))
    )
    with pytest.raises(AppError) as raised:
        call()
    assert raised.value.error_type == "symlink_unsupported"
    assert writes == 0


def test_known_hosts_lock_and_atomic_replace_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = KnownHostsStore(tmp_path / "known_hosts")
    monkeypatch.setattr(os, "open", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("locked")))
    with pytest.raises(AppError) as locked:
        store.verify("a", "ssh-rsa", "SHA256:x", None, persist=True)
    assert locked.value.error_type == "invalid_config"


def test_protocol_times_are_utc_or_null() -> None:
    assert _mlsd_time("20260922010203.25") == "2026-09-22T01:02:03.250000Z"
    assert _mlsd_time("invalid") is None
    assert _mtime(1) == "1970-01-01T00:00:01Z"
    assert _mtime(10**30) is None


def test_preview_first_character_larger_than_budget_is_partial(app_config) -> None:
    result = service_for(app_config, MemoryDriver({"/root/a.txt": "中".encode()})).read_text_preview("/a.txt", 1)
    assert result["content"] == ""
    assert result["truncated"] is True
    assert result["partial_line"] is True
    assert result["returned_lines"] == 0
