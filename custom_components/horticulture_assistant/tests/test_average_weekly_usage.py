import json

from ..utils.nutrient_use_efficiency import NutrientUseEfficiency


def test_average_weekly_usage(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    usage = {
        "plant1": [
            {"date": "2025-01-01", "nutrients": {"N": 100}, "stage": "veg"},
            {"date": "2025-01-08", "nutrients": {"N": 150}, "stage": "veg"},
        ]
    }
    (data_dir / "nutrient_use.json").write_text(json.dumps(usage))
    (data_dir / "yield_logs.json").write_text("{}")
    monkeypatch.chdir(tmp_path)
    nue = NutrientUseEfficiency()
    avg = nue.average_weekly_usage("plant1")
    assert avg["N"] == 125.0
