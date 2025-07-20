from plant_engine.nutrient_manager import (
    get_recommended_levels,
    calculate_deficiencies,
    calculate_nutrient_balance,
)


def test_get_recommended_levels():
    levels = get_recommended_levels("citrus", "fruiting")
    assert levels["N"] == 120
    assert levels["K"] == 100


def test_calculate_deficiencies():
    current = {"N": 60, "P": 50, "K": 100, "Ca": 50, "Mg": 20}
    defs = calculate_deficiencies(current, "tomato", "fruiting")
    assert defs["N"] == 20
    assert defs["K"] == 20


def test_calculate_nutrient_balance():
    current = {"N": 60, "P": 50, "K": 100}
    ratios = calculate_nutrient_balance(current, "tomato", "fruiting")
    # dataset tomato fruiting: N 80, P 60, K 120
    assert ratios["N"] == 0.75
    assert round(ratios["P"], 2) == round(50 / 60, 2)
    assert round(ratios["K"], 2) == round(100 / 120, 2)
