from plant_engine.environment_tips import get_environment_tips, list_supported_plants


def test_environment_tips_basic():
    tips = get_environment_tips("citrus")
    assert tips["high_temp"].startswith("Provide shade")
    assert "citrus" in list_supported_plants()


def test_environment_tips_unknown():
    assert get_environment_tips("unknown") == {}

