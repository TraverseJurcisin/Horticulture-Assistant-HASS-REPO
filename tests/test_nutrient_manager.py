from plant_engine.nutrient_manager import (
    get_recommended_levels,
    calculate_deficiencies,
    calculate_nutrient_balance,
    calculate_surplus,
    calculate_adjustments,
    get_npk_ratio,
    score_nutrient_levels,
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


def test_calculate_surplus():
    current = {"N": 150, "P": 70, "K": 130}
    surplus = calculate_surplus(current, "tomato", "fruiting")
    assert surplus["N"] == 70
    assert surplus["P"] == 10
    assert surplus["K"] == 10


def test_get_recommended_levels_case_insensitive():
    levels = get_recommended_levels("Citrus", "FRUITING")
    assert levels["N"] == 120


def test_get_npk_ratio():
    ratio = get_npk_ratio("tomato", "fruiting")
    assert round(ratio["N"] + ratio["P"] + ratio["K"], 2) == 1.0
    assert ratio["N"] == 0.31
    assert ratio["P"] == 0.23
    assert ratio["K"] == 0.46


def test_score_nutrient_levels():
    # Perfect match yields 100
    current = {"N": 80, "P": 60, "K": 120}
    score = score_nutrient_levels(current, "tomato", "fruiting")
    assert score == 100.0

    # 50% deficit on all nutrients yields 50
    deficit = {"N": 40, "P": 30, "K": 60}
    score = score_nutrient_levels(deficit, "tomato", "fruiting")
    assert 49.9 < score < 50.1


def test_blueberry_guidelines():
    levels = get_recommended_levels("blueberry", "fruiting")
    assert levels["K"] == 80


def test_calculate_adjustments():
    current = {"N": 50, "P": 15, "K": 90}
    adj = calculate_adjustments(current, "blueberry", "vegetative")
    assert adj["N"] == 10  # target 60
    assert adj["P"] == 5   # target 20
    assert adj["K"] == -30  # target 60 -> surplus
