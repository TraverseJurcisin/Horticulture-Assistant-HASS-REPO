import json
import plant_engine.nutrient_efficiency as ne


def setup_data(tmp_path):
    n_dir = tmp_path / "nutes"
    y_dir = tmp_path / "yield"
    n_dir.mkdir()
    y_dir.mkdir()
    (n_dir / "p1.json").write_text(json.dumps({"records": [{"nutrients_mg": {"N": 1000}}]}))
    (y_dir / "p1.json").write_text(json.dumps({"harvests": [{"yield_grams": 1000}]}))
    return n_dir, y_dir


def test_calculate_nue_report(tmp_path, monkeypatch):
    n_dir, y_dir = setup_data(tmp_path)
    monkeypatch.setattr(ne, "NUTRIENT_DIR", str(n_dir))
    monkeypatch.setattr(ne, "YIELD_DIR", str(y_dir))
    monkeypatch.setattr(ne, "load_dataset", lambda _: {"tomato": {"N": 5.0}})
    rep = ne.calculate_nue_report("p1", "tomato")
    assert rep.plant_id == "p1"
    assert rep.total_yield_g == 1000
    assert rep.nue["N"] == 1000.0
    assert rep.evaluation["N"]["status"] == "above target"

