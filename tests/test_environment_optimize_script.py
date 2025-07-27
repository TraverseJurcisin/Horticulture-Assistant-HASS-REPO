from pathlib import Path
import subprocess
import sys
import json

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/environment_optimize.py"


def test_cli_basic():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "vegetative", "--env", '{"temp_c":25,"humidity_pct":60}'],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "setpoints" in data
    assert "adjustments" in data

