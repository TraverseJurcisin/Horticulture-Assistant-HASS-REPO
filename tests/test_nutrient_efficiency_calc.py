import json

from plant_engine import nutrient_efficiency


def test_calculate_nue(tmp_path, monkeypatch):
    nutrient_dir = tmp_path / "nutrients"
    yield_dir = tmp_path / "yield"
    nutrient_dir.mkdir()
    yield_dir.mkdir()

    # Nutrients applied
    nutrient_log = {
        "records": [
            {"nutrients_mg": {"N": 1000, "K": 500}},
            {"nutrients_mg": {"N": 500, "K": 250}},
        ]
    }
    (nutrient_dir / "plant.json").write_text(json.dumps(nutrient_log))

    # Yield data
    yield_data = {"harvests": [{"yield_grams": 1500}]}
    (yield_dir / "plant.json").write_text(json.dumps(yield_data))

    monkeypatch.setattr(nutrient_efficiency, "NUTRIENT_DIR", str(nutrient_dir))
    monkeypatch.setattr(nutrient_efficiency, "YIELD_DIR", str(yield_dir))

    result = nutrient_efficiency.calculate_nue("plant")
    assert result["total_yield_g"] == 1500
    assert result["nue"]["N"] == 1000.0  # 1500g / 1.5g
    assert result["nue"]["K"] == 2000.0  # 1500g / 0.75g
