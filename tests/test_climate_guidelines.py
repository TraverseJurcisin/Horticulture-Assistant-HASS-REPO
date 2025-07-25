from plant_engine.environment_manager import (
    get_climate_guidelines,
    get_combined_environment_guidelines,
    get_combined_environmental_targets,
    recommend_climate_adjustments,
    get_environmental_targets,
)


def test_get_climate_guidelines():
    guide = get_climate_guidelines("temperate")
    assert guide.temp_c == (18.0, 28.0)
    assert guide.humidity_pct == (60.0, 80.0)


def test_recommend_climate_adjustments():
    env = {"temp_c": 30, "humidity_pct": 50, "light_ppfd": 700, "co2_ppm": 500}
    rec = recommend_climate_adjustments(env, "temperate")
    assert "temperature" in rec and rec["temperature"].startswith("lower")
    assert "humidity" in rec and rec["humidity"].startswith("increase")
    assert "light" in rec and rec["light"].startswith("lower")
    assert "co2" in rec and rec["co2"].startswith("raise")


def test_get_combined_environment_guidelines():
    guide = get_combined_environment_guidelines("citrus", "seedling", "temperate")
    assert guide.temp_c == (22, 26)
    assert guide.light_ppfd == (250, 300)
    assert guide.co2_ppm == (600, 600)


def test_get_combined_environmental_targets_default():
    combined = get_combined_environmental_targets("citrus", "seedling")
    plant_only = get_environmental_targets("citrus", "seedling")
    assert combined == plant_only
