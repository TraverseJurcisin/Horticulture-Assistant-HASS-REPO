import json
from custom_components.horticulture_assistant.utils.nutrient_use_efficiency import NutrientUseEfficiency


def test_nutrient_efficiency_basic(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "nutrient_use.json").write_text(json.dumps({
        "plant1": [
            {"date": "2025-01-01", "nutrients": {"N": 100}, "stage": "veg"}
        ]
    }))
    (data_dir / "yield_logs.json").write_text(json.dumps({
        "plant1": [
            {"date": "2025-01-05", "weight": 500}
        ]
    }))
    monkeypatch.chdir(tmp_path)
    nue = NutrientUseEfficiency()
    eff = nue.compute_efficiency("plant1")
    assert eff == {"N": 5.0}
    summary = nue.get_usage_summary("plant1", "month")
    assert summary["2025-01"]["N"] == 100


def test_log_and_save(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "nutrient_use.json").write_text("{}")
    (data_dir / "yield_logs.json").write_text("{}")
    monkeypatch.chdir(tmp_path)
    nue = NutrientUseEfficiency()
    nue.log_fertilizer_application("p2", {"P": 50})
    nue.log_yield("p2", 200)
    assert nue.total_nutrients_applied("p2")["P"] == 50
    assert nue.yield_log["p2"] == 200
    data = json.loads((data_dir / "nutrient_use.json").read_text())
    assert data["p2"][0]["nutrients"]["P"] == 50


def test_compare_to_targets(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "nutrient_use.json").write_text(
        json.dumps({"plant1": [{"date": "2025-01-01", "nutrients": {"N": 100, "P": 30}, "stage": "veg"}]})
    )
    (data_dir / "yield_logs.json").write_text(
        json.dumps({"plant1": [{"date": "2025-01-05", "weight": 700}]})
    )
    monkeypatch.chdir(tmp_path)
    nue = NutrientUseEfficiency()
    diff = nue.compare_to_targets("plant1", "tomato")
    assert diff["N"] == 0.0
    assert diff["P"] > 0
