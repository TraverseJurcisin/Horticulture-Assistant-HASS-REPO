from ..engine.plant_engine import silicon_manager as si


def test_silicon_guidelines():
    levels = si.get_recommended_levels("lettuce", "seedling")
    assert levels["Si"] == 20


def test_silicon_deficiencies():
    current = {"Si": 10}
    defs = si.calculate_deficiencies(current, "lettuce", "seedling")
    assert defs["Si"] == 10


def test_silicon_surplus():
    current = {"Si": 50}
    surplus = si.calculate_surplus(current, "tomato", "fruiting")
    assert surplus["Si"] == 10
