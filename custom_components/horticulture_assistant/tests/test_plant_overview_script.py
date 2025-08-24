import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/plant_overview.py"


def test_plant_overview_cli(tmp_path: Path):
    out_file = tmp_path / "overview.json"
    subprocess.run(
        [sys.executable, str(SCRIPT), "tomato", "--output", str(out_file)],
        check=True,
    )
    data = json.loads(out_file.read_text())
    assert "nutrients" in data
    assert "environment" in data


def test_plant_overview_cli_stdout():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "tomato"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert "pests" in data
