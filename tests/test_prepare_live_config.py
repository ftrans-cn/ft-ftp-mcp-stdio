from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_live_config.py"


def test_prepare_live_config_requires_explicit_missing_root_override(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    destination = tmp_path / "isolated" / "config.json"
    source.write_text(
        json.dumps(
            {
                "version": 1,
                "default_server": "ftp1",
                "servers": [
                    {
                        "alias": "ftp1",
                        "protocol": "ftp",
                        "host": "example.invalid",
                        "port": 21,
                        "username": "test",
                        "readOnly": False,
                        "max_batch_files": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rejected = subprocess.run(
        [sys.executable, str(SCRIPT), str(source), str(destination)],
        capture_output=True,
        check=False,
        text=True,
    )
    assert rejected.returncode != 0
    assert not destination.exists()

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(source),
            str(destination),
            "--root",
            "ftp1=/",
            "--writable",
            "ftp1",
        ],
        check=True,
    )
    result = json.loads(destination.read_text(encoding="utf-8"))
    assert result["version"] == 2
    assert result["log_usage"] is False
    assert result["servers"][0]["root"] == "/"
    assert result["servers"][0]["readOnly"] is False
    assert "max_batch_files" not in result["servers"][0]
    assert Path(result["staging_dir"]) == destination.parent / "staging"
