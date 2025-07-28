from custom_components.horticulture_assistant.utils.nutrient_requirements import (
    get_requirements,
    calculate_deficit,
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

