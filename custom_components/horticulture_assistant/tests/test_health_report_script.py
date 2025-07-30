from pathlib import Path
import json
import subprocess
import sys

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/health_report.py"

def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data))


def test_health_report_cli(tmp_path: Path):
    env = tmp_path / "env.json"
    nuts = tmp_path / "nutrients.json"
    _write_json(env, {"temp_c": 20, "humidity_pct": 70})
    _write_json(nuts, {"N": 60, "P": 20})
    out_file = tmp_path / "report.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "citrus",
            "vegetative",
            "--env",
            str(env),
            "--nutrients",
            str(nuts),
            "--output",
            str(out_file),
        ],
        check=True,
    )
    data = json.loads(out_file.read_text())
    assert "environment" in data
    assert "deficiencies" in data


def test_health_report_cli_stdout(tmp_path: Path):
    env = tmp_path / "env.json"
    nuts = tmp_path / "nutrients.json"
    _write_json(env, {"temp_c": 20, "humidity_pct": 70})
    _write_json(nuts, {"N": 60})
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "citrus",
            "vegetative",
            "--env",
            str(env),
            "--nutrients",
            str(nuts),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert "pest_actions" in data

