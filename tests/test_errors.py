from ftplib import error_perm

import pytest

from ft_ftp_mcp_stdio.errors import map_exception


def test_maps_ftp_permission_errors_to_chinese_semantic_error() -> None:
    error = map_exception(Exception("550 Permission denied"), "上传文件")
    assert error.error_type == "permission_denied"
    assert "上传文件被服务器拒绝" in error.message
    assert error.retryable is False


def test_server_error_is_not_retryable() -> None:
    error = map_exception(Exception("unexpected server response"))
    assert error.error_type == "server_error"
    assert error.retryable is False


def test_only_controlled_errors_allow_details() -> None:
    from ft_ftp_mcp_stdio.errors import AppError

    with pytest.raises(ValueError, match="does not allow"):
        AppError("server_error", "failed", details={"unsafe": True})
    with pytest.raises(ValueError, match="requires"):
        AppError("outcome_unknown", "unknown")


@pytest.mark.parametrize("response", ["550 Permission denied", "553 File name not allowed", "Permission denied"])
def test_maps_error_perm_to_permission_denied(response: str) -> None:
    error = map_exception(error_perm(response), "目录操作")
    assert error.error_type == "permission_denied"
    assert error.retryable is False


def test_maps_ftp_530_to_credential_error() -> None:
    error = map_exception(error_perm("530 Login incorrect"), "FTP 登录")
    assert error.error_type == "credential_missing"
    assert error.retryable is False
