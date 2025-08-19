from plant_engine.nutrient_recovery import (
    get_recovery_factor,
    get_recovery_factors,
    estimate_recovered_amounts,
    adjust_for_recovery,
)


def test_get_recovery_factor_default():
    assert get_recovery_factor("N") == 0.5


def test_get_recovery_factor_override():
    assert get_recovery_factor("N", "tomato") == 0.6


def test_get_recovery_factors():
    factors = get_recovery_factors("tomato")
    assert factors["N"] == 0.6
    assert factors["P"] == 0.35


def test_estimate_recovered_amounts():
    recovered = estimate_recovered_amounts({"P": 100}, "lettuce")
    assert recovered == {"P": 30.0}


def test_adjust_for_recovery():
    adjusted = adjust_for_recovery({"K": 100})
    assert adjusted == {"K": 40.0}
