from ..engine.plant_engine import water_usage as water_usage


def test_estimate_stage_total_use():
    assert water_usage.estimate_stage_total_use("lettuce", "vegetative") == 6300.0
    # stage not defined in usage or duration returns 0
    assert water_usage.estimate_stage_total_use("tomato", "flowering") == 0.0


def test_estimate_cycle_total_use():
    assert water_usage.estimate_cycle_total_use("lettuce") == 12000.0
