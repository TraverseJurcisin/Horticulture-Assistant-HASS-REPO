import json

import plant_engine.water_efficiency as we


def setup_yield(tmp_path):
    y_dir = tmp_path / "yield"
    y_dir.mkdir()
    yield_data = {"harvests": [{"yield_grams": 300}]}
    (y_dir / "plant.json").write_text(json.dumps(yield_data))
    return y_dir


def test_calculate_wue(tmp_path, monkeypatch):
    y_dir = setup_yield(tmp_path)
    monkeypatch.setattr(we, "YIELD_DIR", y_dir)
    wue = we.calculate_wue("plant", "lettuce")
    assert round(wue, 2) == 25.0


def test_evaluate_wue(tmp_path, monkeypatch):
    y_dir = setup_yield(tmp_path)
    monkeypatch.setattr(we, "YIELD_DIR", y_dir)
    wue = we.calculate_wue("plant", "lettuce")
    result = we.evaluate_wue(wue, "lettuce")
    assert result["status"] == "within target"
