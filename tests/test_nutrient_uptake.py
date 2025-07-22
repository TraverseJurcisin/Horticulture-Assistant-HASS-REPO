import pytest

from plant_engine.nutrient_uptake import list_supported_plants, get_daily_uptake
from plant_engine.fertigation import recommend_uptake_fertigation


def test_get_daily_uptake():
    uptake = get_daily_uptake("lettuce", "vegetative")
    assert uptake["N"] == 60
    assert uptake["K"] == 80


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "lettuce" in plants


def test_recommend_uptake_fertigation():
    schedule = recommend_uptake_fertigation("lettuce", "vegetative", num_plants=2)
    assert schedule["urea"] == pytest.approx((60*2)/1000/0.46, rel=1e-2)
    assert schedule["map"] == pytest.approx((20*2)/1000/0.22, rel=1e-2)
    assert schedule["kcl"] == pytest.approx((80*2)/1000/0.5, rel=1e-2)
