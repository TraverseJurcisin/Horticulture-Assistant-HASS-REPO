import json
import subprocess
import sys
from pathlib import Path

from scripts.precision_fertigation import load_water_profile

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


def test_load_water_profile(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text('{"ec":1.2}')
    assert load_water_profile(str(path)) == {"ec": 1.2}

    missing = tmp_path / "missing.json"
    assert load_water_profile(str(missing)) == {}
