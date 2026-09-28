from __future__ import annotations

import os
import stat
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .errors import AppError


class KnownHostsStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_name(path.name + ".lock")

    def verify(self, alias: str, algorithm: str, fingerprint: str, expected: str | None, *, persist: bool) -> None:
        with self._lock():
            records = self._read()
            if expected is not None and expected != fingerprint:
                raise AppError("permission_denied", "SFTP 主机密钥校验失败")
            known = records.get(alias)
            if expected is None and known is not None and known != (algorithm, fingerprint):
                raise AppError("permission_denied", "SFTP 主机密钥与已保存的信任记录不一致")
            if persist and known != (algorithm, fingerprint):
                records[alias] = (algorithm, fingerprint)
                self._write(records)

    def records(self) -> dict[str, tuple[str, str]]:
        with self._lock():
            return self._read()

    def inspect(self) -> dict[str, tuple[str, str]]:
        """Read diagnostic state without creating a lock file or directory."""
        return self._read()

    def _read(self) -> dict[str, tuple[str, str]]:
        if not self.path.exists():
            return {}
        try:
            if os.name != "nt" and stat.S_IMODE(self.path.stat().st_mode) & 0o077:
                raise AppError("invalid_config", "known-hosts 文件权限不安全")
            records: dict[str, tuple[str, str]] = {}
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) != 3:
                    raise AppError("invalid_config", "known-hosts 文件格式损坏")
                alias, algorithm, fingerprint = parts
                value = (algorithm, fingerprint)
                if alias in records:
                    raise AppError("invalid_config", "known-hosts 包含重复服务器记录")
                records[alias] = value
            return records
        except AppError:
            raise
        except (OSError, UnicodeError) as exc:
            raise AppError("invalid_config", "known-hosts 无法安全读取") from exc

    def _write(self, records: dict[str, tuple[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                for alias, (algorithm, fingerprint) in sorted(records.items()):
                    handle.write(f"{alias} {algorithm} {fingerprint}\n")
                handle.flush()
                os.fsync(handle.fileno())
            if os.name != "nt":
                temporary.chmod(0o600)
            os.replace(temporary, self.path)
        except OSError as exc:
            temporary.unlink(missing_ok=True)
            raise AppError("invalid_config", "known-hosts 无法安全持久化") from exc

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + 5
        descriptor: int | None = None
        while descriptor is None:
            try:
                descriptor = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise AppError("invalid_config", "known-hosts 无法取得跨进程锁")
                time.sleep(0.05)
            except OSError as exc:
                raise AppError("invalid_config", "known-hosts 无法取得跨进程锁") from exc
        try:
            yield
        finally:
            os.close(descriptor)
            try:
                self.lock_path.unlink()
            except OSError as exc:
                raise AppError("invalid_config", "known-hosts 锁无法安全释放") from exc
