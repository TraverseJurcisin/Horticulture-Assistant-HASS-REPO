import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/generate_guideline_summary.py"


def test_cli_json():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "fruiting"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data["environment"]["temp_c"] == [18, 28]
    assert "aphids" in data["pest_guidelines"]


def test_cli_yaml():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "fruiting", "--yaml"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "temp_c" in result.stdout
