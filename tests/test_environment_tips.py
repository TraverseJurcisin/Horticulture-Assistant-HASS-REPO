from plant_engine.environment_tips import get_environment_tips, list_supported_plants


def test_environment_tips_basic():
    tips = get_environment_tips("citrus")
    assert tips["high_temp"].startswith("Provide shade")
    assert "citrus" in list_supported_plants()

    lettuce = get_environment_tips("lettuce")
    assert lettuce["high_temp"].startswith("Provide shade")
    assert "lettuce" in list_supported_plants()


def test_environment_tips_stage_specific():
    tips = get_environment_tips("citrus", "fruiting")
    assert tips["low_temp"].startswith("Use heaters")


def test_environment_tips_unknown():
    assert get_environment_tips("unknown") == {}

