import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/nutrient_deficit.py"


def test_nutrient_deficit_cli(tmp_path):
    totals_file = tmp_path / "totals.json"
    totals_file.write_text('{"N": 50, "P": 20}')
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "citrus", str(totals_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    out = result.stdout.strip()
    assert '"N": 100' in out
    assert '"P": 30' in out
    assert '"K": 150' in out
