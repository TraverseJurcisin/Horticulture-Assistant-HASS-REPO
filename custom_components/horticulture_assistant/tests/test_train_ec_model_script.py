from pathlib import Path
import subprocess
import sys
import csv
import json

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/train_ec_model.py"

def test_train_ec_model_cli(tmp_path: Path):
    csv_file = tmp_path / "samples.csv"
    with open(csv_file, "w", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["moisture", "temperature", "irrigation_ml", "solution_ec", "observed_ec"],
        )
        writer.writeheader()
        writer.writerow({"moisture": 30, "temperature": 20, "irrigation_ml": 100, "solution_ec": 1.2, "observed_ec": 1.0})
        writer.writerow({"moisture": 40, "temperature": 22, "irrigation_ml": 150, "solution_ec": 1.5, "observed_ec": 1.4})

    out_file = tmp_path / "model.json"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            str(csv_file),
            "--output",
            str(out_file),
            "--plant-id",
            "plant1",
            "--base-path",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out_file.exists()
    data = json.loads(out_file.read_text())
    assert isinstance(data.get("coeffs"), dict)
    assert "intercept" in data
    assert result.stdout
