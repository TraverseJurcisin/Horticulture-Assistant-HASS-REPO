import pytest

from ..engine.plant_engine.nutrient_uptake import (
    estimate_area_cumulative_uptake,
    estimate_area_total_uptake,
    estimate_stage_totals,
    estimate_total_uptake,
)


def test_estimate_stage_totals():
    totals = estimate_stage_totals("lettuce", "vegetative")
    assert totals["N"] == 60 * 35
    assert totals["K"] == 80 * 35


def test_estimate_total_uptake():
    totals = estimate_total_uptake("lettuce")
    assert totals["N"] == 60 * 35 + 50 * 30
    assert totals["P"] == 20 * 35 + 15 * 30
    assert totals["K"] == 80 * 35 + 70 * 30


def test_estimate_area_total_uptake():
    totals = estimate_area_total_uptake("lettuce", 1.0)
    plants = 1.0 / (0.25**2)
    expected_n = (60 * 35 + 50 * 30) * plants
    assert totals["N"] == pytest.approx(expected_n, rel=1e-2)


def test_estimate_area_cumulative_uptake():
    totals = estimate_area_cumulative_uptake("lettuce", "vegetative", 1.0)
    plants = 1.0 / (0.25**2)
    expected_n = 60 * 35 * plants
    assert totals["N"] == pytest.approx(expected_n, rel=1e-2)
