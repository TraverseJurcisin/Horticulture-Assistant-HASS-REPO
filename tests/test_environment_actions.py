from plant_engine.environment_manager import recommend_environment_actions


def test_recommend_environment_actions_increase():
    readings = {"temperature": 10}
    actions = recommend_environment_actions(readings, "citrus", "vegetative")
    assert actions["temperature"].startswith("enable")


def test_recommend_environment_actions_none_when_in_range():
    readings = {"temp_c": 20, "humidity_pct": 60}
    actions = recommend_environment_actions(readings, "citrus", "vegetative")
    assert actions == {}
