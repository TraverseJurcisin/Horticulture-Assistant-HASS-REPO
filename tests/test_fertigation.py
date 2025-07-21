from plant_engine.fertigation import (
    recommend_fertigation_schedule,
    recommend_correction_schedule,
    get_fertilizer_purity,
    recommend_batch_fertigation,
    recommend_fertigation_with_water_profile,
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


def test_fertigation_with_water_profile():
    schedule, warnings = recommend_fertigation_with_water_profile(
        "citrus",
        "vegetative",
        volume_l=1.0,
        water_profile={"N": 10, "Na": 60},
        product="urea",
    )
    assert "Na" in warnings
    expected = round((0.08 / 0.46) - (0.01 / 0.46), 3)
    assert round(schedule["N"], 3) == expected


