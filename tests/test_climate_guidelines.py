from plant_engine.environment_manager import (
    get_climate_guidelines,
    recommend_climate_adjustments,
)


def test_get_climate_guidelines():
    guide = get_climate_guidelines("temperate")
    assert guide.temp_c == (18.0, 28.0)
    assert guide.humidity_pct == (60.0, 80.0)


def test_recommend_climate_adjustments():
    env = {"temp_c": 30, "humidity_pct": 50}
    rec = recommend_climate_adjustments(env, "temperate")
    assert "temperature" in rec and rec["temperature"].startswith("lower")
    assert "humidity" in rec and rec["humidity"].startswith("increase")
