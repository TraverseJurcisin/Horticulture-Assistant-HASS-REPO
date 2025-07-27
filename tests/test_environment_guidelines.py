from plant_engine.environment_manager import (
    get_environment_guidelines,
    get_environmental_targets,
    get_seasonal_environment_guidelines,
    get_seasonal_environmental_targets,
)


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


def test_get_seasonal_environment_guidelines_winter():
    guide = get_seasonal_environment_guidelines("citrus", "seedling", season="winter")
    assert guide.temp_c == (20.0, 24.0)
    assert guide.humidity_pct == (65.0, 85.0)


def test_get_seasonal_environmental_targets_matches_dataclass():
    guide = get_seasonal_environment_guidelines("citrus", "seedling", season="summer")
    targets = get_seasonal_environmental_targets("citrus", "seedling", season="summer")
    assert targets == guide.as_dict()
