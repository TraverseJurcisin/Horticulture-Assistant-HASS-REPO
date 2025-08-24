import plant_engine.water_usage as water_usage


def test_estimate_daily_use_from_et0():
    # lettuce vegetative stage kc=1.0, spacing 25 cm => area 0.0625 m2
    use = water_usage.estimate_daily_use_from_et0("lettuce", "vegetative", et0_mm_day=5.0)
    assert use > 0
    assert round(use, 1) == round(5.0 * 1.0 * 0.0625 * 1000, 1)

    # unknown plant => 0
    assert water_usage.estimate_daily_use_from_et0("unknown", "stage", 5.0) == 0.0
