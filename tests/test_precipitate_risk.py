from plant_engine.precipitate_risk import (
    list_supported_plants,
    estimate_precipitate_risk,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "iris" in plants


def test_estimate_precipitate_risk():
    nutrients = {"Fe": 1.0, "P": 10.0}
    risk = estimate_precipitate_risk("iris", nutrients, ph=6.5, ec=1.2)
    assert "Fe_P" in risk
    assert "FePO4" in risk["Fe_P"]
    risk = estimate_precipitate_risk("iris", nutrients, ph=6.0, ec=1.2)
    assert risk == {}
