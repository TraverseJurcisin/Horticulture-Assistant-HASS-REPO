from ..engine.plant_engine.hardiness_zone import get_min_temperature, suitable_zones


def test_get_min_temperature():
    assert get_min_temperature("5") == -23
    assert get_min_temperature("unknown") is None


def test_suitable_zones():
    zones = suitable_zones(-20)
    assert "6" in zones and "7" in zones
    assert "5" not in zones
