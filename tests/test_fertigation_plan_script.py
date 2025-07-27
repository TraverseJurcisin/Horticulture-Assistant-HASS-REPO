from pathlib import Path
import subprocess
import sys
import json

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/fertigation_plan.py"


def test_fertigation_plan_cli(tmp_path: Path):
    out_file = tmp_path / "plan.json"
    subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "vegetative", "2", "--output", str(out_file)],
        check=True,
    )
    data = json.loads(out_file.read_text())
    assert "1" in data
    assert isinstance(data["1"], dict)
