from plant_engine.precipitation_risk import (
    list_supported_plants,
    estimate_precipitation_risk,
)


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "iris" in plants
    assert "citrus" in plants


def test_estimate_precipitation_risk_high():
    dosing = {"Fe": 1.0, "P": 0.5}
    risk = estimate_precipitation_risk("iris", dosing, ph=6.5, ec=1.2)
    assert risk["Fe_P"]["level"] == "high"
    assert "EDDHA" in risk["Fe_P"]["message"]


def test_estimate_precipitation_risk_none():
    dosing = {"Fe": 1.0, "P": 0.5}
    risk = estimate_precipitation_risk("iris", dosing, ph=6.2, ec=1.0)
    assert risk == {}
