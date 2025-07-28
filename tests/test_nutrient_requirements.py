from custom_components.horticulture_assistant.utils.nutrient_requirements import (
    get_requirements,
    calculate_deficit,
    calculate_daily_area_requirements,
)


def test_get_requirements():
    req = get_requirements("citrus")
    assert req["N"] == 150
    assert req["K"] == 150


def test_calculate_deficit():
    deficits = calculate_deficit({"N": 100, "P": 20}, "citrus")
    assert deficits["N"] == 50
    assert deficits["P"] == 30
    assert deficits["K"] == 150


def test_calculate_daily_area_requirements():
    req = calculate_daily_area_requirements("citrus", 10, "fruiting")
    assert req == {"N": 726.0, "P": 242.0, "K": 726.0}

