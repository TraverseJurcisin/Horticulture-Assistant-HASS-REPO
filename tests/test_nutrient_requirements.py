from custom_components.horticulture_assistant.utils.nutrient_requirements import (
    get_requirements,
    calculate_deficit,
    calculate_cumulative_requirements,
)


def test_get_requirements():
    req = get_requirements("citrus")
    assert req["N"] == 150
    assert req["K"] == 150


def test_get_requirements_blueberry():
    req = get_requirements("blueberry")
    assert req["N"] == 100
    assert req["P"] == 40
    assert req["K"] == 100


def test_calculate_deficit():
    deficits = calculate_deficit({"N": 100, "P": 20}, "citrus")
    assert deficits["N"] == 50
    assert deficits["P"] == 30
    assert deficits["K"] == 150


def test_cumulative_requirements():
    totals = calculate_cumulative_requirements("tomato", 7)
    assert totals["N"] == 1260  # 180 * 7
    assert totals["P"] == 420
    assert totals["K"] == 1400

