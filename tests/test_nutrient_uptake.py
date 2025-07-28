import pytest

from plant_engine.nutrient_uptake import (
    list_supported_plants,
    get_daily_uptake,
    get_uptake_ratio,
    estimate_average_daily_uptake,
    estimate_cumulative_uptake,
    estimate_area_daily_uptake,
    estimate_area_stage_uptake,
)
from plant_engine.fertigation import recommend_uptake_fertigation


def test_get_daily_uptake():
    uptake = get_daily_uptake("lettuce", "vegetative")
    assert uptake["N"] == 60
    assert uptake["K"] == 80


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "lettuce" in plants
    assert "citrus" in plants
    assert "pepper" in plants
    assert "kale" in plants


def test_recommend_uptake_fertigation():
    schedule = recommend_uptake_fertigation("lettuce", "vegetative", num_plants=2)
    assert schedule["urea"] == pytest.approx((60*2)/1000/0.46, rel=1e-2)
    assert schedule["map"] == pytest.approx((20*2)/1000/0.22, rel=1e-2)
    assert schedule["kcl"] == pytest.approx((80*2)/1000/0.5, rel=1e-2)


def test_get_uptake_ratio():
    ratio = get_uptake_ratio("citrus", "vegetative")
    assert ratio == {"N": 0.4, "P": 0.12, "K": 0.48}


def test_estimate_average_daily_uptake():
    avg = estimate_average_daily_uptake("tomato")
    assert avg == {"N": 51.67, "P": 15.83, "K": 60.0}


def test_estimate_cumulative_uptake():
    totals = estimate_cumulative_uptake("lettuce", "vegetative")
    assert totals["N"] == 60 * 35
    assert totals["K"] == 80 * 35


def test_estimate_area_daily_uptake():
    daily = estimate_area_daily_uptake("lettuce", "vegetative", 1.0)
    plants = 1.0 / (0.25 ** 2)
    assert daily["N"] == pytest.approx(60 * plants, rel=1e-2)
    assert daily["K"] == pytest.approx(80 * plants, rel=1e-2)


def test_estimate_area_stage_uptake():
    totals = estimate_area_stage_uptake("lettuce", "vegetative", 1.0)
    duration = 35
    plants = 1.0 / (0.25 ** 2)
    assert totals["N"] == pytest.approx(60 * plants * duration, rel=1e-2)
    assert totals["K"] == pytest.approx(80 * plants * duration, rel=1e-2)
