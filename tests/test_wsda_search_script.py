from pathlib import Path
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/wsda_search.py"


def test_search_cli(tmp_path):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "EARTH-CARE", "--limit", "1"],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert lines
    assert any("EARTH-CARE" in line for line in lines)


def test_number_cli():
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "(#4083-0001)", "--number"],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout
    assert "N" in out and "K" in out
