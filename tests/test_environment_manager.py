from plant_engine.environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
)


def test_get_environmental_targets_seedling():
    data = get_environmental_targets("citrus", "seedling")
    assert data["temp_c"] == [22, 26]
    assert data["humidity_pct"] == [60, 80]
    assert data["light_ppfd"] == [150, 300]
    assert data["co2_ppm"] == [400, 600]


def test_recommend_environment_adjustments():
    actions = recommend_environment_adjustments(
        {
            "temp_c": 18,
            "humidity_pct": 90,
            "light_ppfd": 100,
            "co2_ppm": 700,
        },
        "citrus",
        "seedling",
    )
    assert actions["temperature"] == "increase"
    assert actions["humidity"] == "decrease"
    assert actions["light"] == "increase"
    assert actions["co2"] == "decrease"


def test_recommend_environment_adjustments_no_data():
    actions = recommend_environment_adjustments({"temp_c": 20}, "unknown")
    assert actions == {}
