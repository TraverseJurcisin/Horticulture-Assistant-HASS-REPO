import pytest
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
    mix = recommend_nutrient_mix(
        "tomato", "vegetative", 10.0, current_levels=current
    )
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
