from plant_engine.fertigation import (
    recommend_fertigation_schedule,
    recommend_correction_schedule,
)


def test_recommend_fertigation_schedule():
    result = recommend_fertigation_schedule(
        "citrus",
        "fruiting",
        volume_l=10.0,
        purity={"N": 0.2},
    )
    assert round(result["N"], 2) == 6.0


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
