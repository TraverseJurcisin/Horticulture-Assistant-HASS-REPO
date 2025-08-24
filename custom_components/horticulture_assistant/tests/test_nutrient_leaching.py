import pytest
from plant_engine.nutrient_leaching import (
    compensate_for_leaching,
    estimate_cumulative_leaching_loss,
    estimate_leaching_loss,
    get_leaching_rate,
    project_levels_after_leaching,
)


def test_get_leaching_rate_default():
    assert get_leaching_rate("N") == 0.2


def test_get_leaching_rate_override():
    assert get_leaching_rate("N", "tomato") == 0.25


def test_estimate_leaching_loss():
    losses = estimate_leaching_loss({"N": 100, "P": 50}, "lettuce")
    assert losses == {"N": 15.0, "P": 2.5}


def test_compensate_for_leaching():
    adjusted = compensate_for_leaching({"K": 100})
    assert adjusted == {"K": 115.0}


def test_estimate_cumulative_leaching_loss():
    losses = estimate_cumulative_leaching_loss({"N": 100}, "tomato", 3)
    expected = 100 * (1 - (1 - 0.25) ** 3)
    assert round(losses["N"], 2) == round(expected, 2)
    with pytest.raises(ValueError):
        estimate_cumulative_leaching_loss({"N": 100}, "tomato", 0)


def test_project_levels_after_leaching():
    remaining = project_levels_after_leaching({"N": 100}, "lettuce", 2)
    expected = 100 * (1 - 0.15) ** 2
    assert round(remaining["N"], 2) == round(expected, 2)
