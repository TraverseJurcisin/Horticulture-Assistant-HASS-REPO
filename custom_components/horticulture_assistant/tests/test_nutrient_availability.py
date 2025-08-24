from plant_engine.nutrient_availability import (
    availability_factor,
    availability_for_all,
    get_optimal_ph,
    list_supported_nutrients,
)


def test_list_supported_nutrients():
    nutrients = list_supported_nutrients()
    assert "N" in nutrients
    assert "P" in nutrients


def test_get_optimal_ph():
    rng = get_optimal_ph("N")
    assert isinstance(rng, tuple) and len(rng) == 2


def test_availability_factor_inside_range():
    rng = get_optimal_ph("P")
    assert rng is not None
    low, high = rng
    assert availability_factor("P", (low + high) / 2) == 1.0


def test_availability_factor_outside_range():
    rng = get_optimal_ph("K")
    assert rng is not None
    high = rng[1]
    assert availability_factor("K", high + 2.0) < 1.0


def test_availability_for_all():
    factors = availability_for_all(6.5)
    assert set(list_supported_nutrients()) == set(factors)
