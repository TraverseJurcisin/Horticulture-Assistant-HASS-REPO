from pathlib import Path
import json
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pest_plan.py"


def test_pest_plan_cli(tmp_path: Path):
    out_file = tmp_path / "plan.json"
    subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "aphids", "scale", "--output", str(out_file)],
        check=True,
    )
    data = json.loads(out_file.read_text())
    assert "aphids" in data
    assert "treatment" in data["aphids"]


def test_pest_plan_cli_stdout():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "aphids"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "aphids" in data
