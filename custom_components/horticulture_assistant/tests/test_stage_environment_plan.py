from ..engine.plant_engine.environment_manager import generate_stage_environment_plan


def test_generate_stage_environment_plan_citrus_seedling():
    plan = generate_stage_environment_plan("citrus")
    assert "seedling" in plan
    seedling = plan["seedling"]
    # midpoint of [22, 26]
    assert seedling["temp_c"] == 24
    # soil moisture midpoint [30, 50] -> 40
    assert seedling["soil_moisture_pct"] == 40
