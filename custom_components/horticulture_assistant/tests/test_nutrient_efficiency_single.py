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

def test_calculate_nue_for_nutrient(tmp_path, monkeypatch):
    n_dir, y_dir = setup_data(tmp_path)
    monkeypatch.setattr(ne, "NUTRIENT_DIR", str(n_dir))
    monkeypatch.setattr(ne, "YIELD_DIR", str(y_dir))
    nue_n = ne.calculate_nue_for_nutrient("plant", "N")
    nue_k = ne.calculate_nue_for_nutrient("plant", "K")
    assert round(nue_n, 2) == 1333.33  # 2kg yield / 1.5g N
    assert round(nue_k, 2) == 4000.0   # 2kg yield / 0.5g K

def test_calculate_nue_for_nutrient_missing(tmp_path, monkeypatch):
    n_dir, y_dir = setup_data(tmp_path)
    monkeypatch.setattr(ne, "NUTRIENT_DIR", str(n_dir))
    monkeypatch.setattr(ne, "YIELD_DIR", str(y_dir))
    assert ne.calculate_nue_for_nutrient("plant", "Ca") is None
