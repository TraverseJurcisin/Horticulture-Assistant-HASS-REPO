from plant_engine.nutrient_absorption import (
    get_absorption_rates,
    apply_absorption_rates,
    list_stages,
)


def test_get_absorption_rates():
    rates = get_absorption_rates("seedling")
    assert rates["N"] == 0.6
    assert "seedling" in list_stages()


def test_apply_absorption_rates():
    schedule = {"N": 10.0, "K": 5.0}
    adjusted = apply_absorption_rates(schedule, "seedling")
    assert adjusted["N"] == 16.67
    assert adjusted["K"] == 7.14
