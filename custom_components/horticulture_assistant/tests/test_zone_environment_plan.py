from plant_engine.environment_manager import (
    generate_zone_environment_plan,
    suggest_environment_setpoints_zone,
)


def test_suggest_environment_setpoints_zone():
    result = suggest_environment_setpoints_zone("citrus", "seedling", "temperate")
    assert result["temp_c"] == 24
    assert result["humidity_pct"] == 70
    assert result["light_ppfd"] == 275
    assert result["co2_ppm"] == 600


def test_generate_zone_environment_plan():
    plan = generate_zone_environment_plan("citrus", "temperate")
    assert plan["seedling"]["light_ppfd"] == 275
