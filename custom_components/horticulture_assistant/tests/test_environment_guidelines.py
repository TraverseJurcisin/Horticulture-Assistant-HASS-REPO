from ..engine.plant_engine.environment_manager import get_environment_guidelines, get_environmental_targets


def test_get_environment_guidelines_dataclass():
    guide = get_environment_guidelines("citrus", "seedling")
    assert guide.temp_c == (22.0, 26.0)
    assert guide.humidity_pct == (60.0, 80.0)
    assert guide.light_ppfd == (150.0, 300.0)
    assert guide.co2_ppm == (400.0, 600.0)


def test_get_environmental_targets_matches_dataclass():
    guide_dict = get_environmental_targets("citrus", "seedling")
    guide = get_environment_guidelines("citrus", "seedling")
    assert guide_dict == guide.as_dict()
