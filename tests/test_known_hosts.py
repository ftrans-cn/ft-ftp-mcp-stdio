from __future__ import annotations

import os
from pathlib import Path

import pytest

from ft_ftp_mcp_stdio.errors import AppError
from ft_ftp_mcp_stdio.known_hosts import KnownHostsStore


def test_first_use_persists_algorithm_and_fingerprint_atomically(tmp_path: Path) -> None:
    path = tmp_path / "known_hosts"
    store = KnownHostsStore(path)
    store.verify("sftp1", "ssh-ed25519", "SHA256:abc", None, persist=True)
    assert path.read_text(encoding="utf-8") == "sftp1 ssh-ed25519 SHA256:abc\n"
    assert not path.with_name("known_hosts.lock").exists()


def test_config_fingerprint_is_checked_and_synchronized(tmp_path: Path) -> None:
    path = tmp_path / "known_hosts"
    KnownHostsStore(path).verify("sftp1", "ssh-rsa", "SHA256:abc", "SHA256:abc", persist=True)
    assert "ssh-rsa" in path.read_text(encoding="utf-8")
    with pytest.raises(AppError) as raised:
        KnownHostsStore(path).verify("sftp1", "ssh-rsa", "SHA256:other", "SHA256:abc", persist=True)
    assert raised.value.error_type == "permission_denied"


def test_explicit_fingerprint_replaces_stale_known_host_atomically(tmp_path: Path) -> None:
    path = tmp_path / "known_hosts"
    path.write_text("sftp1 ssh-rsa SHA256:old\nother ssh-ed25519 SHA256:keep\n", encoding="utf-8")
    KnownHostsStore(path).verify("sftp1", "ssh-ed25519", "SHA256:new", "SHA256:new", persist=True)
    assert path.read_text(encoding="utf-8") == (
        "other ssh-ed25519 SHA256:keep\n"
        "sftp1 ssh-ed25519 SHA256:new\n"
    )


def test_failed_explicit_fingerprint_update_preserves_old_file(monkeypatch, tmp_path: Path) -> None:
    path = tmp_path / "known_hosts"
    original = b"sftp1 ssh-rsa SHA256:old\n"
    path.write_bytes(original)
    monkeypatch.setattr(os, "replace", lambda *args: (_ for _ in ()).throw(PermissionError("blocked")))
    with pytest.raises(AppError) as raised:
        KnownHostsStore(path).verify("sftp1", "ssh-ed25519", "SHA256:new", "SHA256:new", persist=True)
    assert raised.value.error_type == "invalid_config"
    assert path.read_bytes() == original


@pytest.mark.parametrize("content", ["broken\n", "a ssh-rsa one\na ssh-rsa one\n", "a ssh-rsa one\na ssh-rsa two\n"])
def test_malformed_or_duplicate_records_fail_closed(tmp_path: Path, content: str) -> None:
    path = tmp_path / "known_hosts"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(AppError) as raised:
        KnownHostsStore(path).records()
    assert raised.value.error_type == "invalid_config"


def test_read_only_verification_does_not_persist_tofu(tmp_path: Path) -> None:
    path = tmp_path / "known_hosts"
    KnownHostsStore(path).verify("sftp1", "ssh-ed25519", "SHA256:abc", None, persist=False)
    assert not path.exists()


def test_conflicting_known_key_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "known_hosts"
    path.write_text("sftp1 ssh-ed25519 SHA256:old\n", encoding="utf-8")
    with pytest.raises(AppError) as raised:
        KnownHostsStore(path).verify("sftp1", "ssh-ed25519", "SHA256:new", None, persist=True)
    assert raised.value.error_type == "permission_denied"
