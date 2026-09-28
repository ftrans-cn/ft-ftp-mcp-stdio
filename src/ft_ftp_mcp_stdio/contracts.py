from __future__ import annotations

from copy import deepcopy
from typing import Any

ERROR_TYPES = (
    "invalid_config",
    "credential_missing",
    "invalid_argument",
    "not_found",
    "invalid_path",
    "symlink_unsupported",
    "policy_rejected",
    "size_limit_exceeded",
    "permission_denied",
    "connection_unavailable",
    "integrity_check_failed",
    "server_error",
    "outcome_unknown",
)

OBJECT_TYPES = ("file", "dir", "symlink", "other")
BATCH_ERROR_TYPES = (
    "not_found",
    "invalid_path",
    "policy_rejected",
    "permission_denied",
    "connection_unavailable",
    "integrity_check_failed",
    "server_error",
)


def _object(properties: dict[str, Any], required: tuple[str, ...] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required or properties),
        "additionalProperties": False,
    }


def _nullable(schema: dict[str, Any]) -> dict[str, Any]:
    return {"anyOf": [schema, {"type": "null"}]}


STRING = {"type": "string", "minLength": 1}
INTEGER = {"type": "integer", "minimum": 0}
MTIME = _nullable({"type": "string", "pattern": r"Z$"})
OBJECT_TYPE = {"type": "string", "enum": list(OBJECT_TYPES)}

EVIDENCE_ITEM = _object(
    {
        "kind": {"type": "string", "enum": ["pre_state", "post_state", "ftp_unique", "remote_hash", "size", "mtime"]},
        "result": {"type": "string", "enum": ["matched", "mismatched", "unavailable", "check_failed"]},
        "path": STRING,
    }
)

UPLOAD_LIMIT_DETAILS = _object(
    {
        "limit_kind": {"const": "upload_file_bytes"},
        "configured_limit": {"type": "integer", "minimum": 1},
        "observed_value": {"type": "integer", "minimum": 2},
        "observation": {"type": "string", "enum": ["exact", "at_least"]},
        "remote_committed": {"const": False},
    }
)

OUTCOME_UNKNOWN_DETAILS = _object(
    {
        "operation": {"type": "string", "enum": ["upload_file", "upload_dir", "make_dir", "rename", "move", "delete"]},
        "phase": {"type": "string", "enum": ["request_dispatched", "remote_execution", "response_wait", "postcondition_check"]},
        "paths": {"type": "array", "items": STRING, "minItems": 1},
        "evidence": {"type": "array", "items": EVIDENCE_ITEM},
    }
)


def error_schema() -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    for error_type in ERROR_TYPES:
        properties: dict[str, Any] = {
            "ok": {"const": False},
            "error_type": {"const": error_type},
            "message": STRING,
            "retryable": {"const": False},
            "hint": STRING,
        }
        required = ["ok", "error_type", "message", "retryable"]
        if error_type == "size_limit_exceeded":
            properties["details"] = UPLOAD_LIMIT_DETAILS
            required.append("details")
        elif error_type == "outcome_unknown":
            properties["details"] = OUTCOME_UNKNOWN_DETAILS
            required.append("details")
        variants.append(_object(properties, tuple(required)))
    return {"type": "object", "oneOf": variants}


def result_schema(success: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "oneOf": [deepcopy(success), *deepcopy(error_schema()["oneOf"])]}


ENTRY = _object({"name": STRING, "type": OBJECT_TYPE, "size": _nullable(INTEGER), "mtime": MTIME})
MATCH = _object({"path": STRING, "type": OBJECT_TYPE, "size": _nullable(INTEGER), "mtime": MTIME})
BATCH_FAILED = _object({"path": STRING, "error_type": {"type": "string", "enum": list(BATCH_ERROR_TYPES)}, "message": STRING})
SYMLINK_SKIPPED = _object({"path": STRING, "reason_type": {"const": "symlink_unsupported"}, "message": STRING})
LIMIT_SKIPPED = _object(
    {"path": STRING, "reason_type": {"const": "size_limit_exceeded"}, "message": STRING, "details": UPLOAD_LIMIT_DETAILS}
)
BATCH_SKIPPED = {"oneOf": [SYMLINK_SKIPPED, LIMIT_SKIPPED]}
BATCH_INDETERMINATE = _object(
    {
        "path": STRING,
        "error_type": {"const": "outcome_unknown"},
        "message": STRING,
        "evidence": {"type": "array", "items": EVIDENCE_ITEM},
    }
)

SUCCESS_SCHEMAS: dict[str, dict[str, Any]] = {
    "list_servers": _object({"ok": {"const": True}, "servers": {"type": "array", "items": _object({
        "alias": STRING, "description": _nullable(STRING), "protocol": {"type": "string", "enum": ["ftp", "sftp"]},
        "read_only": {"type": "boolean"}, "is_default": {"type": "boolean"},
    })}}),
    "test_connection": _object({"ok": {"const": True}, "server": STRING, "protocol": {"type": "string", "enum": ["ftp", "sftp"]}, "read_only": {"type": "boolean"}}),
    "list_dir": _object({"ok": {"const": True}, "path": STRING, "entries": {"type": "array", "items": ENTRY}, "truncated": {"type": "boolean"}}),
    "search_files": _object({"ok": {"const": True}, "path": STRING, "matches": {"type": "array", "items": MATCH}, "truncated": {"type": "boolean"}}),
    "get_file_info": _object({"ok": {"const": True}, "path": STRING, "type": OBJECT_TYPE, "size": _nullable(INTEGER), "mtime": MTIME}),
    "read_text_preview": _object({"ok": {"const": True}, "path": STRING, "content": {"type": "string"}, "encoding": {"type": "string", "enum": ["utf-8", "utf-8-sig", "gbk"]}, "truncated": {"type": "boolean"}, "returned_lines": INTEGER, "total_lines": _nullable(INTEGER), "partial_line": {"type": "boolean"}}),
    "download_file": _object({"ok": {"const": True}, "remote_path": STRING, "local_path": STRING, "size": INTEGER, "mtime": MTIME, "sha256": STRING}),
    "upload_file": _object({"ok": {"const": True}, "remote_path": STRING, "size": INTEGER, "status": {"const": "completed"}}),
    "make_dir": _object({"ok": {"const": True}, "path": STRING, "created": {"type": "boolean"}, "status": {"const": "completed"}}),
    "rename": _object({"ok": {"const": True}, "old_path": STRING, "new_path": STRING, "type": OBJECT_TYPE, "status": {"const": "completed"}}),
    "move": _object({"ok": {"const": True}, "from_path": STRING, "to_path": STRING, "type": OBJECT_TYPE, "status": {"const": "completed"}}),
    "delete": _object({"ok": {"const": True}, "path": STRING, "type": OBJECT_TYPE, "status": {"const": "completed"}}),
    "download_dir": _object({"ok": {"const": True}, "remote_path": STRING, "local_dir": STRING, "file_count": INTEGER, "total_size": INTEGER, "skipped": {"type": "array", "items": SYMLINK_SKIPPED}, "failed": {"type": "array", "items": BATCH_FAILED}, "status": {"type": "string", "enum": ["complete", "partial", "failed"]}}),
    "upload_dir": _object({"ok": {"const": True}, "remote_path": STRING, "file_count": INTEGER, "total_size": INTEGER, "skipped": {"type": "array", "items": BATCH_SKIPPED}, "failed": {"type": "array", "items": BATCH_FAILED}, "indeterminate": {"type": "array", "items": BATCH_INDETERMINATE}, "status": {"type": "string", "enum": ["complete", "partial", "failed", "indeterminate"]}}),
}


OUTPUT_SCHEMAS = {name: result_schema(schema) for name, schema in SUCCESS_SCHEMAS.items()}
