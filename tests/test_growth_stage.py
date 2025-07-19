from plant_engine.growth_stage import get_stage_info


def test_get_stage_info():
    info = get_stage_info("tomato", "flowering")
    assert info["duration_days"] == 20
