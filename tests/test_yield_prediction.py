import importlib
import json

import plant_engine.yield_prediction as yp
from plant_engine import yield_manager


def test_get_estimated_yield(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "yield_estimates.json").write_text(json.dumps({"tomato": 100}))
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    importlib.reload(yp)
    assert yp.get_estimated_yield("tomato") == 100


def test_estimate_remaining_yield(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "yield_estimates.json").write_text(json.dumps({"tomato": 100}))
    yield_dir = tmp_path / "yield"
    yield_dir.mkdir()
    harvest_data = {"harvests": [{"date": "2024-01-01", "yield_grams": 30}]}
    (yield_dir / "plant1.json").write_text(json.dumps(harvest_data))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("HORTICULTURE_YIELD_DIR", str(yield_dir))
    importlib.reload(yield_manager)
    importlib.reload(yp)

    remaining = yp.estimate_remaining_yield("plant1", "tomato")
    assert remaining == 70
