from plant_engine.nutrient_schedule import generate_daily_uptake_plan


def test_generate_daily_uptake_plan_strawberry():
    plan = generate_daily_uptake_plan("strawberry")
    assert "vegetative" in plan
    veg = plan["vegetative"]
    assert len(veg) == 60
    first_day = veg[1]
    assert first_day["N"] == 14.0
    assert first_day["P"] == 6.0
    assert first_day["K"] == 16.0
