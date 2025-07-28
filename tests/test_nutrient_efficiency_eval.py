import json
import plant_engine.nutrient_efficiency as ne

def setup_data(tmp_path):
    nutrient_dir = tmp_path / "nutes"
    yield_dir = tmp_path / "yield"
    nutrient_dir.mkdir()
    yield_dir.mkdir()
    nutrient_log = {"records": [{"nutrients_mg": {"N": 1000, "K": 500}}, {"nutrients_mg": {"N": 500}}]}
    (nutrient_dir / "plant.json").write_text(json.dumps(nutrient_log))
    yield_data = {"harvests": [{"yield_grams": 2000}]}
    (yield_dir / "plant.json").write_text(json.dumps(yield_data))
    return nutrient_dir, yield_dir

def test_evaluate_plant_nue(tmp_path, monkeypatch):
    n_dir, y_dir = setup_data(tmp_path)
    monkeypatch.setattr(ne, "NUTRIENT_DIR", str(n_dir))
    monkeypatch.setattr(ne, "YIELD_DIR", str(y_dir))
    # override dataset loader
    monkeypatch.setattr(ne, "load_dataset", lambda _: {"tomato": {"N": 5.0, "K": 6.0}})
    result = ne.evaluate_plant_nue("plant", "tomato")
    assert result["N"]["status"] == "above target"
    assert result["K"]["status"] == "above target"


def test_recommend_nue_improvements(tmp_path, monkeypatch):
    n_dir, y_dir = setup_data(tmp_path)
    monkeypatch.setattr(ne, "NUTRIENT_DIR", str(n_dir))
    monkeypatch.setattr(ne, "YIELD_DIR", str(y_dir))
    monkeypatch.setattr(ne, "_TIPS", {"N": "tip"})
    monkeypatch.setattr(ne, "load_dataset", lambda _: {"tomato": {"N": 10}})
    eval_map = ne.evaluate_plant_nue("plant", "tomato")
    eval_map["N"]["status"] = "below target"
    tips = ne.recommend_nue_improvements(eval_map)
    assert tips["N"] == "tip"

