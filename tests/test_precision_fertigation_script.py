from pathlib import Path
import subprocess
import sys
import json

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/precision_fertigation.py"


def test_cli_json():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "tomato", "vegetative", "5"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "schedule" in data
    assert "injection_volumes" in data


def test_cli_synergy():
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "tomato",
            "vegetative",
            "5",
            "--use-synergy",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "schedule" in data


