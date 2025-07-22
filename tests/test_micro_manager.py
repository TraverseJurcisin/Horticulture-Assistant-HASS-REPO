import plant_engine.micro_manager as micro


def test_micro_guidelines():
    levels = micro.get_recommended_levels("lettuce", "seedling")
    assert levels["Fe"] == 2.0
    assert levels["Mn"] == 0.5


def test_micro_deficiencies():
    current = {"Fe": 1.0, "Mn": 0.2}
    defs = micro.calculate_deficiencies(current, "lettuce", "seedling")
    assert defs["Fe"] == 1.0
    assert defs["Mn"] == 0.3
