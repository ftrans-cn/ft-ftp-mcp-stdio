"""Upload maintained fixtures through the product's v2 virtual-path contract."""

from __future__ import annotations

import argparse
from pathlib import Path

from ft_ftp_mcp_stdio.config import load_config
from ft_ftp_mcp_stdio.service import FileService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="上传测试数据集到隔离的 /mcp_* 虚拟目录")
    parser.add_argument("--server", required=True, help="配置 v2 中的可写服务器 alias")
    parser.add_argument("--remote-root", default="/mcp_fixtures", help="目标虚拟目录，必须以 /mcp_ 开头")
    parser.add_argument("--source", default="fixtures", help="make_fixtures.py 生成的本地目录")
    parser.add_argument("--confirm", action="store_true", help="确认执行远端写入")
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error("upload requires --confirm")
    if not args.remote_root.startswith("/mcp_") or ".." in args.remote_root.split("/"):
        parser.error("remote root must be an absolute /mcp_* virtual path without '..'")
    source = Path(args.source).resolve()
    if not source.is_dir():
        parser.error(f"fixture directory does not exist: {source}")
    result = FileService(load_config()).upload_dir(str(source), args.remote_root, alias=args.server)
    print(result)
    return 0 if result["status"] == "complete" else 1


if __name__ == "__main__":
    raise SystemExit(main())
