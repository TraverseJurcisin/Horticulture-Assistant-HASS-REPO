from plant_engine import drought_manager


def test_list_supported_plants():
    plants = drought_manager.list_supported_plants()
    assert "lettuce" in plants
    assert "pepper" in plants


def test_get_drought_tolerance():
    info = drought_manager.get_drought_tolerance("citrus")
    assert info["tolerance"] == "moderate"
    assert info["max_dry_days"] == 3


def test_recommend_watering_interval():
    assert drought_manager.recommend_watering_interval("pepper") == 4
    assert drought_manager.recommend_watering_interval("unknown", default_days=2) == 2
