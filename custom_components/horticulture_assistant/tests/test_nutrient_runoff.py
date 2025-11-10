import pytest

from plant_engine.nutrient_runoff import (
    compensate_for_runoff,
    estimate_cumulative_runoff_loss,
    estimate_runoff_loss,
    get_runoff_rate,
    project_levels_after_runoff,
)


def test_get_runoff_rate_default():
    assert get_runoff_rate("N") == 0.1


def test_get_runoff_rate_override():
    assert get_runoff_rate("N", "tomato") == 0.15


def test_estimate_runoff_loss():
    losses = estimate_runoff_loss({"N": 100, "P": 50}, "lettuce")
    assert losses == {"N": 12.0, "P": 2.5}


def test_compensate_for_runoff():
    adjusted = compensate_for_runoff({"K": 100})
    assert adjusted == {"K": 108.0}


def test_estimate_cumulative_runoff_loss():
    losses = estimate_cumulative_runoff_loss({"N": 100}, "tomato", 3)
    expected = 100 * (1 - (1 - 0.15) ** 3)
    assert round(losses["N"], 2) == round(expected, 2)
    with pytest.raises(ValueError):
        estimate_cumulative_runoff_loss({"N": 100}, "tomato", 0)


def test_project_levels_after_runoff():
    remaining = project_levels_after_runoff({"N": 100}, "lettuce", 2)
    expected = 100 * (1 - 0.12) ** 2
    assert round(remaining["N"], 2) == round(expected, 2)
