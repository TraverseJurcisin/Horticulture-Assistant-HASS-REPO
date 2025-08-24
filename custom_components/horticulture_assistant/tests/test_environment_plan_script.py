import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/environment_plan.py"


def test_environment_plan_cli(tmp_path: Path):
    out_file = tmp_path / "plan.json"
    subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "--output", str(out_file)],
        check=True,
    )
    data = json.loads(out_file.read_text())
    assert "seedling" in data
    assert "temp_c" in data["seedling"]


def test_environment_plan_cli_zone():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "--zone", "cool"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert "vegetative" in data
