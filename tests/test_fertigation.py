import pytest
from datetime import date
from plant_engine.fertigation import (
    recommend_fertigation_schedule,
    recommend_fertigation_with_water,
    recommend_correction_schedule,
    get_fertilizer_purity,
    recommend_batch_fertigation,
    recommend_nutrient_mix,
    recommend_nutrient_mix_with_water,
    estimate_daily_nutrient_uptake,
    recommend_nutrient_mix_with_cost,
    recommend_nutrient_mix_with_cost_breakdown,
    generate_fertigation_plan,
    calculate_mix_nutrients,
    get_fertigation_interval,
    next_fertigation_date,
)


def test_recommend_fertigation_schedule():
    result = recommend_fertigation_schedule(
        "citrus",
        "fruiting",
        volume_l=10.0,
        purity={"N": 0.2},
    )
    assert round(result["N"], 2) == 6.0


def test_schedule_with_product():
    result = recommend_fertigation_schedule(
        "citrus",
        "vegetative",
        volume_l=10.0,
        product="map",
    )
    # N target 80 ppm -> 800 mg = 0.8 g / 0.11 purity
    assert round(result["N"], 3) == round(0.8 / 0.11, 3)


def test_get_fertilizer_purity():
    purity = get_fertilizer_purity("urea")
    assert purity["N"] == 0.46


def test_recommend_correction_schedule():
    current = {"N": 60, "P": 60}
    result = recommend_correction_schedule(
        current,
        "tomato",
        "fruiting",
        volume_l=5.0,
        purity={"N": 0.5, "P": 0.5},
    )
    # from nutrient_guidelines: N target 80 → deficit 20 ppm × 5 L = 100 mg/0.5 = 0.2 g
    assert round(result["N"], 2) == 0.2
    assert "P" not in result  # no deficiency


def test_correction_with_product():
    result = recommend_correction_schedule(
        {"N": 50},
        "citrus",
        "vegetative",
        volume_l=5.0,
        purity=None,
        product="urea",
    )
    # deficit: N target 80 → diff 30 ppm × 5 L = 150 mg / 0.46 purity
    assert round(result["N"], 3) == round(0.15 / 0.46, 3)


def test_recommend_batch_fertigation():
    batches = recommend_batch_fertigation(
        [("citrus", "vegetative"), ("tomato", "fruiting")],
        volume_l=5.0,
        purity={"N": 1.0},
    )
    assert "citrus-vegetative" in batches
    assert "tomato-fruiting" in batches
    assert batches["citrus-vegetative"]["N"] > 0


def test_recommend_nutrient_mix_full():
    mix = recommend_nutrient_mix("tomato", "vegetative", 10.0)
    assert mix["urea"] == pytest.approx(2.174, rel=1e-3)
    assert mix["map"] == pytest.approx(2.273, rel=1e-3)
    assert mix["kcl"] == pytest.approx(1.6, rel=1e-3)


def test_recommend_nutrient_mix_deficit():
    current = {"N": 60, "P": 30, "K": 60}
    mix = recommend_nutrient_mix("tomato", "vegetative", 10.0, current_levels=current)
    assert mix["urea"] == pytest.approx(0.87, rel=1e-2)
    assert mix["map"] == pytest.approx(0.909, rel=1e-2)
    assert mix["kcl"] == pytest.approx(0.4, rel=1e-2)


def test_recommend_fertigation_with_water():
    schedule, warnings = recommend_fertigation_with_water(
        "tomato",
        "vegetative",
        10.0,
        {"N": 20, "K": 10},
        purity={"N": 1.0, "P": 1.0, "K": 1.0},
    )
    assert warnings == {}
    assert round(schedule["N"], 2) == 0.8
    assert round(schedule["P"], 2) == 0.5
    assert round(schedule["K"], 2) == 0.7


def test_recommend_nutrient_mix_with_water():
    schedule, warnings = recommend_nutrient_mix_with_water(
        "tomato",
        "vegetative",
        10.0,
        {"N": 20, "K": 10},
    )
    assert warnings == {}
    assert schedule["urea"] == pytest.approx(1.739, rel=1e-3)
    assert schedule["map"] == pytest.approx(2.273, rel=1e-3)
    assert schedule["kcl"] == pytest.approx(1.4, rel=1e-3)


def test_estimate_daily_nutrient_uptake():
    uptake = estimate_daily_nutrient_uptake(
        "tomato", "vegetative", daily_water_ml=2000.0
    )
    assert uptake["N"] == pytest.approx(200.0)
    assert uptake["P"] == pytest.approx(100.0)


def test_recommend_nutrient_mix_with_micro():
    mix = recommend_nutrient_mix(
        "lettuce",
        "seedling",
        5.0,
        include_micro=True,
        purity_overrides={"Fe": 1.0},
    )
    assert "chelated_fe" in mix
    assert mix["chelated_fe"] > 0


def test_recommend_nutrient_mix_with_cost():
    schedule, cost = recommend_nutrient_mix_with_cost(
        "citrus",
        "vegetative",
        1.0,
        fertilizers={
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        },
    )
    assert schedule
    assert cost >= 0


def test_recommend_nutrient_mix_with_cost_breakdown():
    schedule, total, breakdown = recommend_nutrient_mix_with_cost_breakdown(
        "citrus",
        "vegetative",
        1.0,
        fertilizers={
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        },
    )
    assert schedule
    assert total >= 0
    assert isinstance(breakdown, dict)
    assert sum(breakdown.values()) == pytest.approx(total, rel=0.1)


def test_generate_fertigation_plan():
    plan = generate_fertigation_plan("lettuce", "seedling", 3)
    assert len(plan) == 3
    day1 = plan[1]
    assert day1["N"] > 0
    assert day1 == plan[2] == plan[3]


def test_calculate_mix_nutrients_wrapper():
    mix = {"foxfarm_grow_big": 9.6}
    totals = calculate_mix_nutrients(mix)
    assert totals["N"] > 0


def test_estimate_daily_nutrient_uptake_invalid():
    with pytest.raises(ValueError):
        estimate_daily_nutrient_uptake("tomato", "vegetative", daily_water_ml=-1)


def test_recommend_uptake_fertigation_invalid():
    from plant_engine.fertigation import recommend_uptake_fertigation

    with pytest.raises(ValueError):
        recommend_uptake_fertigation("lettuce", "vegetative", num_plants=0)


def test_estimate_stage_and_cycle_cost():
    from plant_engine.fertigation import estimate_stage_cost, estimate_cycle_cost

    stage_cost = estimate_stage_cost(
        "lettuce",
        "vegetative",
        fertilizers={
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        },
    )
    cycle_cost = estimate_cycle_cost(
        "lettuce",
        fertilizers={
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        },
    )
    assert stage_cost >= 0
    assert cycle_cost >= stage_cost


def test_recommend_precise_fertigation():
    from plant_engine.fertigation import recommend_precise_fertigation

    schedule, total, breakdown, warnings, diag = recommend_precise_fertigation(
        "tomato",
        "vegetative",
        volume_l=10.0,
        water_profile={"N": 20},
        fertilizers={
            "N": "foxfarm_grow_big",
            "P": "foxfarm_grow_big",
            "K": "intrepid_granular_potash_0_0_60",
        },
        include_micro=False,
    )

    assert schedule
    assert total >= 0
    assert breakdown
    assert warnings == {}
    assert "ppm" in diag


def test_recommend_precise_fertigation_with_injection():
    from plant_engine.fertigation import recommend_precise_fertigation_with_injection

    fert_map = {
        "N": "foxfarm_grow_big",
        "P": "foxfarm_grow_big",
        "K": "intrepid_granular_potash_0_0_60",
    }

    sched, total, breakdown, warnings, diag, inject = recommend_precise_fertigation_with_injection(
        "tomato",
        "vegetative",
        10.0,
        fertilizers=fert_map,
        include_micro=False,
    )

    assert sched
    assert inject
    assert total >= 0


def test_generate_cycle_fertigation_plan():
    from plant_engine.fertigation import generate_cycle_fertigation_plan

    plan = generate_cycle_fertigation_plan("lettuce")
    assert set(plan.keys()) == {"seedling", "vegetative", "harvest"}
    assert len(plan["seedling"]) == 25
    assert len(plan["vegetative"]) == 35
    assert len(plan["harvest"]) == 30
    first_day = plan["seedling"][1]
    assert first_day["N"] > 0


def test_estimate_solution_ec():
    from plant_engine.fertigation import estimate_solution_ec

    schedule = {"N": 100, "K": 150}
    ec = estimate_solution_ec(schedule)
    assert ec == pytest.approx(0.465, rel=1e-3)


def test_generate_cycle_fertigation_plan_with_cost():
    from plant_engine.fertigation import (
        generate_cycle_fertigation_plan,
        generate_cycle_fertigation_plan_with_cost,
    )

    basic_plan = generate_cycle_fertigation_plan("lettuce")
    plan, cost = generate_cycle_fertigation_plan_with_cost("lettuce")

    assert plan == basic_plan
    assert cost >= 0


def test_optimize_fertigation_schedule():
    from plant_engine.fertigation import optimize_fertigation_schedule

    schedule, cost = optimize_fertigation_schedule("citrus", "vegetative", volume_l=1.0)

    assert schedule
    assert "foxfarm_grow_big" in schedule
    assert cost >= 0


def test_grams_to_ppm_roundtrip():
    from plant_engine.fertigation import grams_to_ppm

    schedule = recommend_fertigation_schedule(
        "tomato",
        "vegetative",
        volume_l=10.0,
        purity={"N": 0.5},
    )
    grams = schedule["N"]
    ppm = grams_to_ppm(grams, 10.0, 0.5)
    assert ppm == pytest.approx(100.0)


def test_grams_to_ppm_invalid():
    from plant_engine.fertigation import grams_to_ppm

    with pytest.raises(ValueError):
        grams_to_ppm(1.0, 0.0, 1.0)
    with pytest.raises(ValueError):
        grams_to_ppm(1.0, 1.0, 0.0)


def test_get_fertigation_interval():
    assert get_fertigation_interval("tomato", "vegetative") == 2
    assert get_fertigation_interval("lettuce") == 1
    assert get_fertigation_interval("unknown") is None


def test_next_fertigation_date():
    last = date(2025, 1, 1)
    expected = date(2025, 1, 3)
    assert next_fertigation_date("tomato", "vegetative", last) == expected
    assert next_fertigation_date("unknown", None, last) is None


def test_recommend_stock_solution_injection():
    from plant_engine.fertigation import recommend_stock_solution_injection

    targets = {"N": 150, "P": 50, "K": 120}
    result = recommend_stock_solution_injection(targets, 10.0)
    assert result["stock_a"] == pytest.approx(25.0, rel=1e-3)
    assert result["stock_b"] == pytest.approx(10.0, rel=1e-3)


def test_stock_solution_recipes():
    from plant_engine.fertigation import (
        get_stock_solution_recipe,
        apply_stock_solution_recipe,
    )

    recipe = get_stock_solution_recipe("tomato", "vegetative")
    assert recipe == {"stock_a": 2.0, "stock_b": 1.0}

    scaled = apply_stock_solution_recipe("tomato", "vegetative", 5.0)
    assert scaled == {"stock_a": 10.0, "stock_b": 5.0}


def test_check_solubility_limits():
    from plant_engine.fertigation import check_solubility_limits

    schedule = {
        "foxfarm_grow_big": 400.0,  # 300 g/L limit in dataset
        "magriculture": 500.0,  # 800 g/L limit in dataset
    }
    warnings = check_solubility_limits(schedule, 1.0)
    assert "foxfarm_grow_big" in warnings
    assert "magriculture" not in warnings


def test_validate_fertigation_schedule():
    from plant_engine.fertigation import validate_fertigation_schedule

    schedule = {"foxfarm_grow_big": 300.0}
    diag = validate_fertigation_schedule(schedule, 1.0, "tomato")
    assert "imbalances" in diag and diag["imbalances"]
    assert "toxicities" in diag and diag["toxicities"]


def test_recommend_rootzone_fertigation():
    from plant_engine.fertigation import recommend_rootzone_fertigation
    from plant_engine.rootzone_model import RootZone

    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )

    volume, schedule = recommend_rootzone_fertigation(
        "tomato",
        "vegetative",
        zone,
        available_ml=80.0,
        expected_et_ml=50.0,
    )

    assert volume > 0
    assert schedule["N"] > 0


def test_summarize_fertigation_schedule():
    from plant_engine.fertigation import summarize_fertigation_schedule

    fert_map = {
        "N": "foxfarm_grow_big",
        "P": "foxfarm_grow_big",
        "K": "intrepid_granular_potash_0_0_60",
    }
    summary = summarize_fertigation_schedule(
        "citrus", "vegetative", 1.0, fertilizers=fert_map
    )
    assert "schedule" in summary
    assert "cost_total" in summary
    assert isinstance(summary["schedule"], dict)
    assert summary["cost_total"] >= 0


def test_recommend_loss_compensated_mix():
    from plant_engine.fertigation import (
        recommend_nutrient_mix,
        recommend_loss_compensated_mix,
    )

    base = recommend_nutrient_mix("citrus", "vegetative", 1.0)
    adjusted = recommend_loss_compensated_mix("citrus", "vegetative", 1.0)

    assert adjusted["urea"] > base["urea"]
    assert adjusted["urea"] == pytest.approx(base["urea"] * 1.32, rel=1e-2)
    assert adjusted["map"] == pytest.approx(base["map"] * 1.05, rel=1e-2)


def test_recommend_recovery_adjusted_schedule():
    from plant_engine.fertigation import recommend_recovery_adjusted_schedule

    schedule = recommend_recovery_adjusted_schedule(
        "tomato", "vegetative", 10.0
    )

    assert schedule["N"] == pytest.approx(1.667, rel=1e-3)
    assert schedule["P"] == pytest.approx(1.429, rel=1e-3)
    assert schedule["K"] == pytest.approx(1.231, rel=1e-3)


def test_apply_loss_factors():
    from plant_engine.fertigation import apply_loss_factors

    schedule = {"urea": 1.0, "map": 0.5}
    adjusted = apply_loss_factors(schedule, "citrus")

    assert adjusted["urea"] == pytest.approx(1.08, rel=1e-3)
    assert adjusted["map"] == pytest.approx(0.515, rel=1e-3)


def test_recommend_loss_adjusted_fertigation():
    from plant_engine.fertigation import recommend_loss_adjusted_fertigation

    fert_map = {
        "N": "foxfarm_grow_big",
        "P": "foxfarm_grow_big",
        "K": "intrepid_granular_potash_0_0_60",
    }

    schedule, *_ = recommend_loss_adjusted_fertigation(
        "citrus", "vegetative", 1.0, fertilizers=fert_map
    )

    assert schedule["foxfarm_grow_big"] > 0
    assert schedule["intrepid_granular_potash_0_0_60"] > 0


def test_estimate_weekly_fertigation_cost():
    from plant_engine.fertigation import estimate_weekly_fertigation_cost
    fert_map = {
        "N": "foxfarm_grow_big",
        "P": "foxfarm_grow_big",
        "K": "intrepid_granular_potash_0_0_60",
    }
    cost = estimate_weekly_fertigation_cost(
        "tomato", "vegetative", 10.0, fertilizers=fert_map
    )
    assert cost > 0


def test_cost_optimized_fertigation_injection():
    from plant_engine.fertigation import (
        recommend_cost_optimized_fertigation_with_injection,
    )

    schedule, cost, injection = recommend_cost_optimized_fertigation_with_injection(
        "tomato",
        "vegetative",
        5.0,
    )

    assert schedule
    assert cost >= 0
    assert injection

