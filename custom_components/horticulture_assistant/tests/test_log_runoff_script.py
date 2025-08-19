from pathlib import Path
import subprocess
import sys
import json

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/log_runoff_ec.py"


def test_log_runoff_cli(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "plant1", "1.23", "--base-path", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "Logged runoff EC" in result.stdout
    log = tmp_path / "plant1" / "runoff_ec_log.json"
    assert log.exists()
    data = json.loads(log.read_text())
    assert data and data[0]["ec"] == 1.23
