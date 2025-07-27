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


def test_cli_yaml():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "tomato", "vegetative", "5", "--yaml"],
        capture_output=True,
        text=True,
        check=True,
    )
    import yaml

    data = yaml.safe_load(result.stdout)
    assert "schedule" in data
    assert "injection_volumes" in data

