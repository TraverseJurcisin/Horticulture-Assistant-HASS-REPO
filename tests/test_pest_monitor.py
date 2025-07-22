from plant_engine.pest_monitor import (
    list_supported_plants,
    get_pest_thresholds,
    assess_pest_pressure,
    recommend_threshold_actions,
)


def test_get_pest_thresholds():
    thresh = get_pest_thresholds("citrus")
    assert thresh["aphids"] == 5

    # lookup should be case-insensitive
    thresh2 = get_pest_thresholds("CiTrUs")
    assert thresh2 == thresh


def test_assess_pest_pressure():
    obs = {"aphids": 6, "scale": 1}
    result = assess_pest_pressure("CITRUS", obs)
    assert result["aphids"] is True
    assert result.get("scale") is False


def test_recommend_threshold_actions():
    obs = {"aphids": 6, "scale": 3}
    actions = recommend_threshold_actions("citrus", obs)
    assert "aphids" in actions
    assert "scale" in actions


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "citrus" in plants


def test_recommend_threshold_actions_case_insensitive():
    actions = recommend_threshold_actions("Citrus", {"APHIDS": 6})
    assert "aphids" in actions
