from pathlib import Path
import subprocess
import sys
import json
import os

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/estimate_profit.py"


def test_expected_profit_cli(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "economics").mkdir()
    (data_dir / "yield").mkdir()
    (data_dir / "economics" / "crop_market_prices.json").write_text('{"lettuce": 3}')
    (data_dir / "economics" / "crop_production_costs.json").write_text('{"lettuce": 1}')
    (data_dir / "yield" / "yield_estimates.json").write_text('{"lettuce": 1000}')

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "expected", "lettuce"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "2.0"


def test_actual_profit_cli(tmp_path):
    from plant_engine import yield_manager

    yield_manager.YIELD_DIR = str(tmp_path)
    yield_manager.record_harvest("profitplant", grams=1000)
    env = os.environ.copy()
    env["HORTICULTURE_YIELD_DIR"] = str(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "actual",
            "profitplant",
            "lettuce",
            "--cost",
            "0.5",
            "--cost",
            "0.3",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    assert result.stdout.strip() == "2.2"
