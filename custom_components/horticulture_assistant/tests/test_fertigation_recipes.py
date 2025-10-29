import pytest

from plant_engine.fertigation import (
    apply_fertigation_recipe,
    get_fertigation_recipe,
)


def test_get_fertigation_recipe():
    recipe = get_fertigation_recipe("citrus", "seedling")
    assert recipe == {"urea": 0.5, "map": 0.2, "kcl": 0.3}
    assert get_fertigation_recipe("unknown", "stage") == {}


def test_apply_fertigation_recipe():
    schedule = apply_fertigation_recipe("citrus", "seedling", 10)
    assert schedule["urea"] == 5.0
    assert schedule["map"] == 2.0
    assert schedule["kcl"] == 3.0

    with pytest.raises(ValueError):
        apply_fertigation_recipe("citrus", "seedling", 0)
