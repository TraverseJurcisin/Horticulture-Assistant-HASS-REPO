from plant_engine.nutrient_leaching import (
    get_leaching_rate,
    estimate_leaching_loss,
    compensate_for_leaching,
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
