from plant_engine import thermal_time


def test_calculate_gdd_basic():
    gdd = thermal_time.calculate_gdd(12, 22, base_temp_c=10)
    assert gdd == 7.0


def test_calculate_gdd_no_growth():
    assert thermal_time.calculate_gdd(5, 9, base_temp_c=10) == 0.0


def test_get_stage_requirement():
    assert thermal_time.get_stage_gdd_requirement("lettuce", "vegetative") == 250


def test_predict_stage_completion():
    assert thermal_time.predict_stage_completion("lettuce", "vegetative", 260)
    assert not thermal_time.predict_stage_completion("lettuce", "harvest", 300)


def test_accumulate_gdd_series():
    series = [(10, 20)] * 5
    total = thermal_time.accumulate_gdd_series(series, base_temp_c=10)
    assert total == 25.0
