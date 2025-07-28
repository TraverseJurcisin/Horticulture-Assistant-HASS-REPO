from plant_engine.environment_manager import generate_stage_growth_plan


def test_generate_stage_growth_plan_tomato_seedling():
    plan = generate_stage_growth_plan("tomato")
    assert "seedling" in plan
    seedling = plan["seedling"]
    assert seedling["environment"]["temp_c"] == 24
    assert seedling["nutrients"]["N"] == 90.0
    assert "Transplant seedlings" in " ".join(seedling["tasks"])
