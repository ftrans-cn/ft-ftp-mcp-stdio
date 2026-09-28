from __future__ import annotations

from dataclasses import replace
from ftplib import FTP
from io import BytesIO
from pathlib import Path
from typing import cast

import paramiko
import pytest

from ft_ftp_mcp_stdio.drivers.ftp import FTPDriver
from ft_ftp_mcp_stdio.drivers.sftp import SFTPDriver
from ft_ftp_mcp_stdio.errors import AppError


class FakeDataSocket:
    def __init__(self, data: bytes) -> None:
        self.data = BytesIO(data)

    def recv(self, size: int) -> bytes:
        return self.data.read(size)

    def close(self) -> None:
        self.data.close()


class FakeFTP:
    def __init__(self):
        self.encoding = ""
        self.connected = False
        self.closed = False
        self.stored = None
        self.operations = []

    def connect(self, host, port, timeout):
        self.connected = True
        return "220 ready"

    def login(self, user, password):
        return "230 logged"

    def getwelcome(self):
        return "220 fake"

    def mlsd(self, path):
        return iter([("中文.txt", {"type": "file", "size": "3", "modify": "20260905000000"})])

    def size(self, path):
        if path == "/root/existing.txt":
            return 3
        raise OSError("550 not found")

    def cwd(self, path):
        raise OSError("550 not found")

    def storbinary(self, command, source):
        chunks = []
        while chunk := source.read(64 * 1024):
            chunks.append(chunk)
        self.stored = (command, b"".join(chunks))

    def retrlines(self, command, callback):
        raise OSError("500 LIST unavailable")

    def nlst(self, path):
        raise OSError("500 NLST unavailable")

    def mkd(self, path):
        return path

    def transfercmd(self, command):
        self.operations.append(command)
        return FakeDataSocket(b"preview-data")

    def voidcmd(self, command):
        self.operations.append(command)
        return "200 command okay"

    def voidresp(self):
        return "226 complete"

    def rename(self, source, target):
        self.operations.append(("rename", source, target))

    def delete(self, path):
        self.operations.append(("delete", path))

    def rmd(self, path):
        self.operations.append(("rmd", path))

    def quit(self):
        self.closed = True

    def close(self):
        self.closed = True


def server_config():
    from ft_ftp_mcp_stdio.models import ServerConfig
    return ServerConfig("local", "ftp", "127.0.0.1", 21, "u", root="/root", encoding="gbk")


def test_ftp_driver_sets_configured_encoding_and_lists_entries():
    raw = FakeFTP()
    driver = FTPDriver(server_config(), "pw", lambda: raw)
    assert raw.encoding == "gbk"
    assert driver.list_dir("/root")[0].name == "中文.txt"
    driver.close()
    assert raw.closed is True


def test_ftp_driver_rejects_existing_target_without_overwrite():
    class ExistingFTP(FakeFTP):
        def mlsd(self, path):
            return iter([("existing.txt", {"type": "file", "size": "3"})])

    raw = ExistingFTP()
    driver = FTPDriver(server_config(), "pw", lambda: raw)
    with pytest.raises(AppError, match="已存在") as raised:
        driver.upload(BytesIO(b"data"), "/root/existing.txt", False)
    assert "/root" not in str(raised.value)
    driver.close()


def test_ftp_make_dir_failure_does_not_expose_real_path() -> None:
    class DeniedFTP(FakeFTP):
        def mkd(self, path):
            raise OSError("550 denied")

        def mlsd(self, path):
            return iter([])

    driver = FTPDriver(server_config(), "pw", lambda: cast(FTP, DeniedFTP()))
    with pytest.raises(AppError) as raised:
        driver.make_dir("/root/private/new")
    assert raised.value.error_type == "permission_denied"
    assert "/root" not in str(raised.value)


def test_ftp_upload_returns_complete_size_for_large_file():
    raw = FakeFTP()
    driver = FTPDriver(server_config(), "pw", lambda: raw)
    data = b"x" * (2 * 1024 * 1024 + 137)

    size = driver.upload(BytesIO(data), "/root/large.bin", False)

    assert size == len(data)
    assert raw.stored == ("STOR /root/large.bin", data)


class ListFallbackFTP(FakeFTP):
    def mlsd(self, path):
        raise OSError("500 MLSD unsupported")

    def retrlines(self, command, callback):
        callback("drwxr-xr-x 2 owner group 4096 Sep 10 14:00 报表")
        callback("-rw-r--r-- 1 owner group 123 Sep 10 2026 对账 v2.csv")
        callback("unstructured-name.txt")


def test_ftp_list_dir_falls_back_to_unix_list():
    raw = ListFallbackFTP()
    driver = FTPDriver(server_config(), "pw", lambda: raw)

    entries = driver.list_dir("/")

    assert [(entry.name, entry.type, entry.size) for entry in entries] == [
        ("报表", "dir", 4096),
        ("对账 v2.csv", "file", 123),
        ("unstructured-name.txt", "file", None),
    ]


class NlstFallbackFTP(ListFallbackFTP):
    def retrlines(self, command, callback):
        raise OSError("500 LIST unsupported")

    def nlst(self, path):
        return ["/报表", "/readme.txt"]


def test_ftp_list_dir_falls_back_to_nlst_names():
    driver = FTPDriver(server_config(), "pw", lambda: NlstFallbackFTP())
    entries = driver.list_dir("/")
    assert [(entry.name, entry.type) for entry in entries] == [("报表", "file"), ("readme.txt", "file")]


class AutoEncodingFTP(FakeFTP):
    def mlsd(self, path):
        if self.encoding == "utf-8":
            raise UnicodeDecodeError("utf-8", b"\xb1\xa8", 0, 1, "invalid start byte")
        return iter([("报表.txt", {"type": "file", "size": "4"})])


def test_ftp_auto_encoding_retries_gbk_for_directory_names():
    raw = AutoEncodingFTP()
    config = server_config()
    config = type(config)(**{**config.__dict__, "encoding": "auto"})
    driver = FTPDriver(config, "pw", lambda: raw)

    assert driver.list_dir("/")[0].name == "报表.txt"
    assert raw.encoding == "gbk"


class AutoInfoEncodingFTP(FakeFTP):
    def mlsd(self, path):
        if self.encoding == "utf-8":
            raise UnicodeDecodeError("utf-8", b"\xb1\xa8", 0, 1, "invalid start byte")
        return iter([("报表.txt", {"type": "file", "size": "4"})])


def test_ftp_get_info_auto_encoding_retries_gbk():
    raw = AutoInfoEncodingFTP()
    driver = FTPDriver(replace(server_config(), encoding="auto"), "pw", lambda: raw)
    assert driver.get_info("/root/报表.txt").size == 4
    assert raw.encoding == "gbk"


def test_ftp_get_info_normalizes_mlsd_time_to_utc() -> None:
    raw = FakeFTP()
    driver = FTPDriver(server_config(), "pw", lambda: cast(FTP, raw))
    info = driver.get_info("/root/中文.txt")
    assert info.mtime == "2026-09-05T00:00:00Z"


def test_ftp_get_info_caches_mlsd_unique_identity() -> None:
    class UniqueFTP(FakeFTP):
        def mlsd(self, path):
            return iter([("item.txt", {"type": "file", "size": "3", "unique": "A1B2"})])

    driver = FTPDriver(server_config(), "pw", lambda: cast(FTP, UniqueFTP()))
    assert driver.identity("/root/item.txt") is None
    driver.get_info("/root/item.txt")
    assert driver.identity("/root/item.txt") == "A1B2"


def test_ftp_driver_supports_preview_move_and_delete():
    raw = FakeFTP()
    driver = FTPDriver(server_config(), "pw", lambda: raw)
    assert driver.read_prefix("/root/file.txt", 6) == b"preview"
    driver.move("/root/a", "/root/b")
    driver.delete_file("/root/b")
    driver.delete_dir("/root/empty")
    assert raw.operations == [
        "TYPE I",
        "RETR /root/file.txt",
        ("rename", "/root/a", "/root/b"),
        ("delete", "/root/b"),
        ("rmd", "/root/empty"),
    ]


def test_ftp_get_info_uses_list_fallback_when_mlsd_is_unavailable():
    raw = ListFallbackFTP()
    driver = FTPDriver(server_config(), "pw", lambda: raw)
    info = driver.get_info("/root/报表")
    assert info.type == "dir"
    assert info.size == 4096


class FakeSFTPChannel:
    def __init__(self):
        self.operations = []

    def open(self, path, mode):
        self.operations.append(("open", path, mode))
        return BytesIO(b"sftp-preview")

    def rename(self, source, target):
        self.operations.append(("rename", source, target))

    def remove(self, path):
        self.operations.append(("remove", path))

    def rmdir(self, path):
        self.operations.append(("rmdir", path))

    def close(self):
        return None


class FakeSSHClient:
    def __init__(self):
        self.connect_args: dict[str, object] | None = None
        self.sftp = FakeSFTPChannel()

    def set_missing_host_key_policy(self, policy):
        self.policy = policy

    def connect(self, **kwargs):
        self.connect_args = kwargs

    def open_sftp(self):
        return self.sftp

    def close(self):
        return None


@pytest.mark.parametrize(("passphrase", "expected"), [("", None), ("secret", "secret")])
def test_sftp_private_key_passphrase_is_optional(monkeypatch, passphrase: str, expected: str | None):
    raw = FakeSSHClient()
    config = replace(server_config(), protocol="sftp", port=22, key_path=Path("key.pem"))
    monkeypatch.setattr(SFTPDriver, "_verify_host_key", lambda self, known_hosts, write=True: None)

    driver = SFTPDriver(config, passphrase, Path("known_hosts"), lambda: cast(paramiko.SSHClient, raw))

    assert raw.connect_args is not None
    assert raw.connect_args["passphrase"] == expected
    driver.close()


def test_sftp_driver_supports_preview_move_and_delete(monkeypatch):
    raw = FakeSSHClient()
    config = replace(server_config(), protocol="sftp", port=22)
    monkeypatch.setattr(SFTPDriver, "_verify_host_key", lambda self, known_hosts, write=True: None)
    driver = SFTPDriver(config, "pw", Path("known_hosts"), lambda: cast(paramiko.SSHClient, raw))

    assert driver.read_prefix("/root/file.txt", 4) == b"sftp-"
    driver.move("/root/a", "/root/b")
    driver.delete_file("/root/b")
    driver.delete_dir("/root/empty")
    assert raw.sftp.operations == [
        ("open", "/root/file.txt", "rb"),
        ("rename", "/root/a", "/root/b"),
        ("remove", "/root/b"),
        ("rmdir", "/root/empty"),
    ]


def test_sftp_make_dir_rejects_existing_symlink_segment_without_mkdir() -> None:
    class Attr:
        def __init__(self, mode: int) -> None:
            self.st_mode = mode

    class Channel:
        def __init__(self) -> None:
            self.mkdir_calls: list[str] = []

        def lstat(self, path: str) -> Attr:
            import stat
            return Attr(stat.S_IFLNK if path == "/srv/root/link" else stat.S_IFDIR)

        def mkdir(self, path: str) -> None:
            self.mkdir_calls.append(path)

    channel = Channel()
    driver = object.__new__(SFTPDriver)
    driver.server = replace(server_config(), protocol="sftp", root="/srv/root")
    driver._sftp = cast(paramiko.SFTPClient, channel)
    with pytest.raises(AppError) as raised:
        driver.make_dir("/srv/root/link/new")
    assert raised.value.error_type == "symlink_unsupported"
    assert channel.mkdir_calls == []


def test_sftp_exists_propagates_permission_and_connection_errors() -> None:
    class Channel:
        def __init__(self, error: Exception) -> None:
            self.error = error

        def lstat(self, path: str) -> None:
            raise self.error

    driver = object.__new__(SFTPDriver)
    for error, expected in [(PermissionError("denied"), "permission_denied"), (OSError("offline"), "connection_unavailable")]:
        driver._sftp = cast(paramiko.SFTPClient, Channel(error))
        with pytest.raises(AppError) as raised:
            driver.exists("/root/file")
        assert raised.value.error_type == expected


def test_sftp_type_errors_do_not_expose_real_path() -> None:
    class Attr:
        st_mode = 0o040755
        st_size = 0
        st_mtime = 0

    class Channel:
        def lstat(self, path: str) -> Attr:
            return Attr()

    driver = object.__new__(SFTPDriver)
    driver._sftp = cast(paramiko.SFTPClient, Channel())
    with pytest.raises(AppError) as raised:
        driver.download("/secret/root/directory", BytesIO())
    assert raised.value.error_type == "policy_rejected"
    assert "/secret/root" not in str(raised.value)


def test_sftp_fingerprint_read_only_mode_does_not_create_known_hosts(tmp_path: Path):
    class Key:
        def asbytes(self):
            return b"server-key"

        def get_name(self):
            return "ssh-ed25519"

    class Transport:
        def get_remote_server_key(self):
            return Key()

    class Client:
        def get_transport(self):
            return Transport()

    driver = object.__new__(SFTPDriver)
    driver.server = replace(server_config(), protocol="sftp", port=22)
    driver._client = cast(paramiko.SSHClient, Client())
    known_hosts = tmp_path / "known_hosts"
    driver._verify_host_key(known_hosts, write_known_hosts=False)
    assert not known_hosts.exists()


def test_sftp_host_key_policy_runs_before_authentication_material(tmp_path: Path):
    events: list[str] = []

    class Key:
        def asbytes(self):
            return b"server-key"

        def get_name(self):
            return "ssh-ed25519"

    class OrderedClient(FakeSSHClient):
        def connect(self, **kwargs):
            events.append("host-key")
            self.policy.missing_host_key(cast(paramiko.SSHClient, self), "host", cast(paramiko.PKey, Key()))
            events.append("authentication")
            self.connect_args = kwargs

    raw = OrderedClient()
    config = replace(server_config(), protocol="sftp", port=22)
    known_hosts = tmp_path / "known_hosts"
    SFTPDriver(config, "password", known_hosts, lambda: cast(paramiko.SSHClient, raw)).close()
    assert events == ["host-key", "authentication"]
    assert known_hosts.read_text(encoding="utf-8").startswith("local ssh-ed25519 SHA256:")
