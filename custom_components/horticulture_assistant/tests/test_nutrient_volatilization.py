from plant_engine.nutrient_volatilization import (
    compensate_for_volatilization,
    estimate_volatilization_loss,
    get_volatilization_rate,
)


def test_get_volatilization_rate_default():
    assert get_volatilization_rate("N") == 0.1


def test_get_volatilization_rate_override():
    assert get_volatilization_rate("N", "cabbage") == 0.12


def test_estimate_volatilization_loss():
    losses = estimate_volatilization_loss({"S": 100}, "soybean")
    assert losses == {"S": 5.0}


def test_compensate_for_volatilization():
    adjusted = compensate_for_volatilization({"S": 50})
    assert adjusted == {"S": 51.0}
