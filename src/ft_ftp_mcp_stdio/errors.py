from __future__ import annotations

from dataclasses import dataclass
from ftplib import error_perm
from typing import Any, Literal

from .contracts import ERROR_TYPES

ErrorType = Literal[
    "invalid_config", "credential_missing", "invalid_argument", "not_found", "invalid_path",
    "symlink_unsupported", "policy_rejected", "size_limit_exceeded", "permission_denied",
    "connection_unavailable", "integrity_check_failed", "server_error", "outcome_unknown",
]


@dataclass
class AppError(Exception):
    error_type: ErrorType
    message: str
    hint: str = ""
    details: dict[str, Any] | None = None

    @property
    def retryable(self) -> bool:
        return False

    def __str__(self) -> str:
        return self.message

    def as_result(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "ok": False,
            "error_type": self.error_type,
            "message": self.message,
            "retryable": False,
        }
        if self.hint:
            result["hint"] = self.hint
        if self.details is not None:
            result["details"] = self.details
        return result

    def __post_init__(self) -> None:
        if self.error_type not in ERROR_TYPES:
            raise ValueError(f"Unknown error type: {self.error_type}")
        if self.error_type in {"size_limit_exceeded", "outcome_unknown"}:
            if self.details is None:
                raise ValueError(f"{self.error_type} requires details")
        elif self.details is not None:
            raise ValueError(f"{self.error_type} does not allow details")


def map_exception(exc: Exception, operation: str = "操作") -> AppError:
    text = str(exc)
    upper = text.upper()
    if isinstance(exc, FileNotFoundError) or getattr(exc, "errno", None) == 2:
        return AppError("not_found", f"{operation}失败：远程对象不存在")
    if isinstance(exc, PermissionError) or getattr(exc, "errno", None) in {1, 13}:
        return AppError("permission_denied", f"{operation}被服务器拒绝")
    if "530" in upper:
        return AppError("credential_missing", f"{operation}失败：账号认证失败", "请检查凭据配置。")
    if isinstance(exc, error_perm) or "550" in upper or "553" in upper:
        return AppError(
            "permission_denied",
            f"{operation}被服务器拒绝：账号无权访问目标，或路径不存在",
            "请检查账号权限和服务器路径；部分服务器无法区分无权限与不存在。",
        )
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return AppError(
            "connection_unavailable",
            f"{operation}失败：服务器连接不可用",
            "请检查网络、服务器状态及 FTP 被动端口配置。",
        )
    if "authentication" in text.lower() or "auth" in text.lower():
        return AppError("credential_missing", f"{operation}失败：账号认证失败", "请检查凭据配置。")
    return AppError("server_error", f"{operation}失败：服务器返回未分类错误", "请检查服务器日志。")
