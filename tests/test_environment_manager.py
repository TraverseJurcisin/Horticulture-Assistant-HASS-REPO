import pytest

from plant_engine.environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
    suggest_environment_setpoints,
    calculate_vpd,
)


def test_get_environmental_targets_seedling():
    data = get_environmental_targets("citrus", "seedling")
    assert data["temp_c"] == [22, 26]
    assert data["humidity_pct"] == [60, 80]
    assert data["light_ppfd"] == [150, 300]
    assert data["co2_ppm"] == [400, 600]


def test_recommend_environment_adjustments():
    actions = recommend_environment_adjustments(
        {
            "temp_c": 18,
            "humidity_pct": 90,
            "light_ppfd": 100,
            "co2_ppm": 700,
        },
        "citrus",
        "seedling",
    )
    assert actions["temperature"] == "increase"
    assert actions["humidity"] == "decrease"
    assert actions["light"] == "increase"
    assert actions["co2"] == "decrease"


def test_recommend_environment_adjustments_no_data():
    actions = recommend_environment_adjustments({"temp_c": 20}, "unknown")
    assert actions == {}


def test_suggest_environment_setpoints():
    setpoints = suggest_environment_setpoints("citrus", "seedling")
    assert setpoints["temp_c"] == 24
    assert setpoints["humidity_pct"] == 70
    assert setpoints["light_ppfd"] == 225
    assert setpoints["co2_ppm"] == 500


def test_calculate_vpd():
    vpd = calculate_vpd(25, 50)
    # approx 1.584 kPa using standard formula
    assert round(vpd, 3) == 1.584


def test_calculate_vpd_invalid_humidity():
    with pytest.raises(ValueError):
        calculate_vpd(25, 120)
