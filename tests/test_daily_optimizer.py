from plant_engine.daily_optimizer import build_daily_plan


def test_build_daily_plan():
    plan = build_daily_plan(
        "citrus",
        "vegetative",
        temp_c=42,
        humidity_pct=20,
        wind_m_s=16,
        pests=["aphids"],
        volume_l=1.0,
        include_micro=False,
        water_profile=None,
        fertilizers={
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        },
    )

    assert "temperature" in plan.environment_actions
    assert "humidity" in plan.environment_actions
    assert "wind" in plan.environment_actions
    assert "foxfarm_grow_big" in plan.fertigation_schedule
    assert "aphids" in plan.pest_plan
    assert plan.cost_total >= 0
    assert isinstance(plan.cost_breakdown, dict)
