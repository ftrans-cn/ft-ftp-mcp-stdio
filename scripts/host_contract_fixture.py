from __future__ import annotations

from typing import Any, cast

from ft_ftp_mcp_stdio import server


def upload_dir_result() -> dict[str, object]:
    return {
        "ok": True,
        "remote_path": "/fixture",
        "file_count": 0,
        "total_size": 0,
        "skipped": [],
        "failed": [],
        "indeterminate": [
            {
                "path": "uncertain.txt",
                "error_type": "outcome_unknown",
                "message": "远端写操作的结果无法确认，请人工核验后再决定是否重试",
                "evidence": [
                    {"kind": "post_state", "result": "check_failed", "path": "uncertain.txt"}
                ],
            }
        ],
        "status": "indeterminate",
    }


class FixtureService:
    def upload_dir(
        self,
        local_path: str,
        remote_path: str,
        overwrite: bool = False,
        alias: str | None = None,
    ) -> dict[str, object]:
        del local_path, remote_path, overwrite, alias
        return upload_dir_result()


def main() -> None:
    fixture = FixtureService()
    server._service = cast(Any, lambda config=None: fixture)
    server.record_usage = cast(Any, lambda *args, **kwargs: None)
    server.mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
