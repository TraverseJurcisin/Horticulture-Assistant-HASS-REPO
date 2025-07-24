import pytest
from plant_engine import water_usage


def test_get_daily_use():
    assert water_usage.get_daily_use("lettuce", "vegetative") == 180
    assert water_usage.get_daily_use("tomato", "fruiting") == 320
    assert water_usage.get_daily_use("basil", "vegetative") == 120
    # Unknown plant returns 0
    assert water_usage.get_daily_use("unknown", "stage") == 0.0


def test_list_supported_plants():
    plants = water_usage.list_supported_plants()
    assert "lettuce" in plants
    assert "tomato" in plants
    assert "basil" in plants


def test_estimate_area_use():
    daily = water_usage.estimate_area_use("lettuce", "vegetative", 1.0)
    # spacing 25 cm => 16 plants per m2 * 180 mL
    assert round(daily, 1) == round(1.0 / (0.25 ** 2) * 180, 1)

    daily_unknown = water_usage.estimate_area_use("unknown", "stage", 1.0)
    assert daily_unknown == 0.0

    with pytest.raises(ValueError):
        water_usage.estimate_area_use("lettuce", "vegetative", -1)
