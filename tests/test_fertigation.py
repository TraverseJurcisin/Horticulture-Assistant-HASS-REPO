from plant_engine.fertigation import recommend_fertigation_schedule


def test_recommend_fertigation_schedule():
    result = recommend_fertigation_schedule(
        "citrus",
        "fruiting",
        volume_l=10.0,
        purity={"N": 0.2},
    )
    assert round(result["N"], 2) == 6.0
