from plant_engine.environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
)


def test_get_environmental_targets_seedling():
    data = get_environmental_targets("citrus", "seedling")
    assert data["temp_c"] == [22, 26]
    assert data["humidity_pct"] == [60, 80]


def test_recommend_environment_adjustments():
    actions = recommend_environment_adjustments(
        {"temp_c": 18, "humidity_pct": 90}, "citrus", "seedling"
    )
    assert actions["temperature"] == "increase"
    assert actions["humidity"] == "decrease"


def test_recommend_environment_adjustments_no_data():
    actions = recommend_environment_adjustments({"temp_c": 20}, "unknown")
    assert actions == {}
