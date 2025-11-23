import pytest

from ..engine.plant_engine.water_costs import estimate_water_cost, get_water_cost_rate


def test_get_water_cost_rate():
    assert get_water_cost_rate() == 0.002
    assert get_water_cost_rate("california") == 0.003
    assert get_water_cost_rate("unknown") == 0.002


def test_estimate_water_cost():
    assert estimate_water_cost(10) == 0.02
    assert estimate_water_cost(5, "california") == 0.015
    with pytest.raises(ValueError):
        estimate_water_cost(-1)
