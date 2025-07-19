from plant_engine.nutrient_manager import get_recommended_levels, calculate_deficiencies


def test_get_recommended_levels():
    levels = get_recommended_levels("citrus", "fruiting")
    assert levels["N"] == 120
    assert levels["K"] == 100


def test_calculate_deficiencies():
    current = {"N": 60, "P": 50, "K": 100, "Ca": 50, "Mg": 20}
    defs = calculate_deficiencies(current, "tomato", "fruiting")
    assert defs["N"] == 20
    assert defs["K"] == 20
