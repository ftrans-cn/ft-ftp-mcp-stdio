from __future__ import annotations

import inspect
import logging
import sys
import time
from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any

from fastmcp import FastMCP
from fastmcp.tools import ToolResult
from mcp.types import ToolAnnotations
from pydantic import Field

from . import __version__
from .cli import main as cli_main
from .config import load_config, load_config_for_discovery
from .contracts import OUTPUT_SCHEMAS
from .errors import AppError, map_exception
from .models import AppConfig
from .service import FileService
from .usage_log import record_usage

logging.basicConfig(stream=sys.stderr, level=logging.WARNING, format="%(levelname)s %(message)s")

mcp = FastMCP(
    "ft-ftp-mcp-stdio",
    version=__version__,
    instructions="在已配置的 FTP/SFTP 服务器范围内浏览、读取、传输和管理文件。所有远程路径均为以 / 开头的虚拟绝对路径，并受服务器 root 限制。凭据由本地安全配置读取，不得要求用户在 MCP 会话中提供密码、私钥或口令。写入、覆盖、移动和删除必须遵守工具 Schema、只读策略及客户端确认要求。",
)

Server = Annotated[str | None, Field(description="可选服务器别名；省略时使用默认服务器。")]
RemotePath = Annotated[str, Field(description="服务器虚拟绝对路径，以 / 开头；/ 表示配置的服务器 root。")]
LocalPath = Annotated[str, Field(description="本机绝对路径。")]


def _safe_tool(function: Callable[..., dict[str, Any]]) -> Callable[..., ToolResult]:
    @wraps(function)
    def wrapper(*args: Any, **kwargs: Any) -> ToolResult:
        started = time.perf_counter()
        arguments = dict(inspect.signature(function).bind_partial(*args, **kwargs).arguments)
        is_error = False
        try:
            result = function(*args, **kwargs)
        except AppError as exc:
            result = exc.as_result()
            is_error = True
        except Exception as exc:  # noqa: BLE001
            result = map_exception(exc).as_result()
            is_error = True
        record_usage(function.__name__, arguments, result, time.perf_counter() - started)
        return ToolResult(structured_content=result, is_error=is_error)
    return wrapper


def _service(config: AppConfig | None = None) -> FileService:
    return FileService(config or load_config())


def _annotations(title: str, *, read_only: bool = False, destructive: bool = False, idempotent: bool = True, open_world: bool = True) -> ToolAnnotations:
    return ToolAnnotations(title=title, read_only_hint=read_only, destructive_hint=destructive, idempotent_hint=idempotent, open_world_hint=open_world)


def _tool(name: str, title: str, description: str, annotations: ToolAnnotations) -> Callable[[Callable[..., Any]], Any]:
    return mcp.tool(name=name, title=title, description=description, output_schema=OUTPUT_SCHEMAS[name], annotations=annotations)


@_tool("list_servers", "列出逻辑服务器", "列出可用逻辑服务器的非敏感摘要；不连接远端、不读取凭据，也不触发 TOFU。", _annotations("列出逻辑服务器", read_only=True, open_world=False))
@_safe_tool
def list_servers() -> dict[str, Any]:
    config = load_config_for_discovery()
    return {"ok": True, "servers": []} if config is None else _service(config).list_servers()


@_tool("test_connection", "测试服务器连接", "验证服务器连接和认证；首次 SFTP 连接可能持久化 TOFU 主机密钥。", _annotations("测试服务器连接"))
@_safe_tool
def test_connection(server: Server = None) -> dict[str, Any]:
    return _service().test_connection(server)


@_tool("list_dir", "列出目录", "列出虚拟远程目录的下一层条目；首次 SFTP 连接可能持久化 TOFU 状态。", _annotations("列出目录"))
@_safe_tool
def list_dir(path: RemotePath, server: Server = None) -> dict[str, Any]:
    return _service().list_dir(path, server)


@_tool("search_files", "搜索文件", "在虚拟远程目录下按文件名通配符递归搜索，不进入或返回符号链接。", _annotations("搜索文件"))
@_safe_tool
def search_files(path: RemotePath, pattern: Annotated[str, Field(description="文件名通配符；非空且不能包含路径分隔符。")], server: Server = None) -> dict[str, Any]:
    return _service().search_files(path, pattern, server)


@_tool("get_file_info", "获取文件信息", "返回单个虚拟远程对象的类型、大小和 UTC 修改时间。", _annotations("获取文件信息"))
@_safe_tool
def get_file_info(path: RemotePath, server: Server = None) -> dict[str, Any]:
    return _service().get_file_info(path, server)


@_tool("read_text_preview", "预览文本文件", "按 UTF-8、UTF-8 BOM 或 GBK 解码远程文件前缀，不返回完整连接信息。", _annotations("预览文本文件"))
@_safe_tool
def read_text_preview(path: RemotePath, max_bytes: Annotated[int, Field(description="预览字节预算；业务允许范围为 1 到 1048576。")]=102400, server: Server = None) -> dict[str, Any]:
    return _service().read_text_preview(path, max_bytes, server)


@_tool("download_file", "下载文件", "将单个远程文件下载到本机随机 staging 目录并校验已知大小。", _annotations("下载文件", idempotent=False))
@_safe_tool
def download_file(remote_path: RemotePath, server: Server = None) -> dict[str, Any]:
    return _service().download_file(remote_path, server)


@_tool("upload_file", "上传文件", "通过同目录临时对象安全提交单个本地文件；默认拒绝覆盖。", _annotations("上传文件", destructive=True, idempotent=False))
@_safe_tool
def upload_file(local_path: LocalPath, remote_path: RemotePath, overwrite: Annotated[bool, Field(description="是否请求安全原子覆盖；默认 false。")]=False, server: Server = None) -> dict[str, Any]:
    return _service().upload_file(local_path, remote_path, overwrite, server)


@_tool("make_dir", "创建目录", "在虚拟远程路径创建目录；只读服务器会在连接前拒绝。", _annotations("创建目录"))
@_safe_tool
def make_dir(path: RemotePath, server: Server = None) -> dict[str, Any]:
    return _service().make_dir(path, server)


@_tool("rename", "重命名对象", "在同一虚拟远程目录内重命名对象，不覆盖已有目标。", _annotations("重命名对象", destructive=True, idempotent=False))
@_safe_tool
def rename(path: RemotePath, new_name: Annotated[str, Field(description="不含路径分隔符的新名称。")], server: Server = None) -> dict[str, Any]:
    return _service().rename(path, new_name, server)


@_tool("move", "移动对象", "在同一逻辑服务器的虚拟路径范围内移动对象，不覆盖已有目标。", _annotations("移动对象", destructive=True, idempotent=False))
@_safe_tool
def move(from_path: RemotePath, to_path: RemotePath, server: Server = None) -> dict[str, Any]:
    return _service().move(from_path, to_path, server)


@_tool("delete", "删除对象", "删除单个文件或空目录；confirm 必须在运行时明确为 true。", _annotations("删除对象", destructive=True, idempotent=False))
@_safe_tool
def delete(path: RemotePath, confirm: Annotated[bool, Field(description="用户确认标记；运行时必须为 true。")], server: Server = None) -> dict[str, Any]:
    return _service().delete(path, confirm, server)


@_tool("download_dir", "下载目录", "递归下载目录到随机 staging；逐项报告跳过与失败，不限制文件数量或总字节。", _annotations("下载目录", idempotent=False))
@_safe_tool
def download_dir(remote_path: RemotePath, server: Server = None) -> dict[str, Any]:
    return _service().download_dir(remote_path, server)


@_tool("upload_dir", "上传目录", "逐项上传本地目录。ok=true 仅表示工作流完成；必须检查 status、failed 和 indeterminate，结果不确定时不得整体重试。", _annotations("上传目录", destructive=True, idempotent=False))
@_safe_tool
def upload_dir(local_path: LocalPath, remote_path: RemotePath, overwrite: Annotated[bool, Field(description="是否请求安全原子覆盖；默认 false。")]=False, server: Server = None) -> dict[str, Any]:
    return _service().upload_dir(local_path, remote_path, overwrite, server)


def main() -> None:
    if len(sys.argv) > 1:
        cli_main(sys.argv[1:])
        return
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
