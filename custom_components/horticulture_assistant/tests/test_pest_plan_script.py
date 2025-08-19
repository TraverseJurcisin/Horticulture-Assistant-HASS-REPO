from pathlib import Path
import subprocess
import sys
import json

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/pest_plan.py"


def test_cli_basic():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "aphids"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "aphids" in data
    assert "treatment" in data["aphids"]
