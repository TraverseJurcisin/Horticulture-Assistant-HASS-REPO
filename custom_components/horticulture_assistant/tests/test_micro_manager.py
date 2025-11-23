from ..engine.plant_engine import micro_manager as micro


def test_micro_guidelines():
    levels = micro.get_recommended_levels("lettuce", "seedling")
    assert levels["Fe"] == 2.0
    assert levels["Mn"] == 0.5


def test_micro_deficiencies():
    current = {"Fe": 1.0, "Mn": 0.2}
    defs = micro.calculate_deficiencies(current, "lettuce", "seedling")
    assert defs["Fe"] == 1.0
    assert defs["Mn"] == 0.3


def test_micro_surplus():
    current = {"Fe": 5.0, "Mn": 1.0}
    surplus = micro.calculate_surplus(current, "lettuce", "seedling")
    assert surplus["Fe"] == 3.0
    assert surplus["Mn"] == 0.5


def test_micro_balance():
    current = {"Fe": 1.0, "Mn": 0.25}
    ratios = micro.calculate_balance(current, "lettuce", "seedling")
    assert ratios["Fe"] == 0.5
    assert ratios["Mn"] == 0.5
