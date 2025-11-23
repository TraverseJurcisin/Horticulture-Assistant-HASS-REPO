from ..engine.plant_engine.nighttime_strategy import (
    get_nighttime_strategy,
    list_supported_plants,
    recommend_nighttime_actions,
)


def test_list_supported_plants_contains_known():
    plants = list_supported_plants()
    assert "citrus" in plants
    assert "begonia" in plants


def test_get_nighttime_strategy():
    strat = get_nighttime_strategy("citrus")
    assert strat.get("night_activity") == "growth"


def test_recommend_nighttime_actions():
    actions = recommend_nighttime_actions("begonia")
    assert actions.get("skip_irrigation") is True
    assert actions.get("fertigation_stop_hours") == 2
