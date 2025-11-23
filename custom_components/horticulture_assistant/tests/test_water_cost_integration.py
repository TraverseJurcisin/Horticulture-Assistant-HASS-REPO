from ..engine.plant_engine import water_usage as water_usage


def test_estimate_stage_water_cost():
    cost = water_usage.estimate_stage_water_cost("lettuce", "vegetative")
    assert round(cost, 4) == round(0.002 * 6300 / 1000, 4)


def test_estimate_area_water_cost():
    cost = water_usage.estimate_area_water_cost("lettuce", "vegetative", 1.0)
    expected_ml = water_usage.estimate_area_use("lettuce", "vegetative", 1.0)
    assert round(cost, 4) == round(0.002 * expected_ml / 1000, 4)


def test_estimate_cycle_water_cost():
    cost = water_usage.estimate_cycle_water_cost("lettuce", "california")
    expected_ml = water_usage.estimate_cycle_total_use("lettuce")
    assert round(cost, 4) == round(0.003 * expected_ml / 1000, 4)
