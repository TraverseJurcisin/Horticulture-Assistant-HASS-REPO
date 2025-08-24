import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/monitor_schedule.py"


def test_cli_json():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", "fruiting", "2023-01-01", "3", "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert data == ["2023-01-04", "2023-01-05", "2023-01-07"]
