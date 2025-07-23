from plant_engine import water_usage


def test_get_daily_use():
    assert water_usage.get_daily_use("lettuce", "vegetative") == 180
    assert water_usage.get_daily_use("tomato", "fruiting") == 320
    # Unknown plant returns 0
    assert water_usage.get_daily_use("unknown", "stage") == 0.0


def test_list_supported_plants():
    plants = water_usage.list_supported_plants()
    assert "lettuce" in plants
    assert "tomato" in plants
