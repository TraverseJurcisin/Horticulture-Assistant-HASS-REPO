from ..utils.stage_nutrient_requirements import (
    calculate_stage_deficit,
    get_stage_requirements,
)


def test_get_stage_requirements_fallback():
    # stage data missing -> use totals scaled by multiplier
    req = get_stage_requirements("citrus", "nonexistent")
    assert req["N"] == 150 * 1.0  # multiplier defaults to 1.0


def test_get_stage_requirements_defined():
    req = get_stage_requirements("citrus", "vegetative")
    assert req == {"N": 1.5, "P": 0.5, "K": 1.5}


def test_get_stage_requirements_blueberry():
    req = get_stage_requirements("blueberry", "vegetative")
    assert req == {"N": 1.2, "P": 0.4, "K": 1.2}


def test_calculate_stage_deficit():
    deficits = calculate_stage_deficit({"N": 0.5}, "citrus", "vegetative")
    assert deficits["N"] == 1.0
    assert deficits["P"] == 0.5
    assert deficits["K"] == 1.5
