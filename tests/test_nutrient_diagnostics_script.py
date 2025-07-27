from pathlib import Path
import json
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/nutrient_diagnostics.py"


def test_nutrient_diagnostics(tmp_path: Path):
    levels = {"N": 50, "P": 20, "K": 40}
    file = tmp_path / "levels.json"
    file.write_text(json.dumps(levels))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "lettuce", "seedling", str(file)],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert "deficiencies" in data
    assert data["deficiencies"]
