from custom_components.horticulture_assistant.utils.nutrient_requirements import (
    get_requirements,
    calculate_deficit,
    get_stage_requirements,
    calculate_stage_deficit,
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


def test_get_stage_requirements():
    req = get_stage_requirements("tomato", "vegetative")
    assert req["N"] == 0.8
    assert req["P"] == 0.3


def test_calculate_stage_deficit():
    deficits = calculate_stage_deficit({"N": 0.2, "P": 0.1}, "tomato", "seedling")
    assert deficits["N"] == 0.1
    assert deficits["K"] == 0.3

