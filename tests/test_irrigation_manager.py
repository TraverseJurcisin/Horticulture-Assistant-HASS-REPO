import pytest

from plant_engine.irrigation_manager import (
    recommend_irrigation_volume,
    recommend_irrigation_interval,
    get_crop_coefficient,
    estimate_irrigation_demand,
    recommend_irrigation_from_environment,
    get_daily_irrigation_target,
    list_supported_plants,
    generate_irrigation_schedule,
    adjust_irrigation_for_efficiency,
)
from plant_engine.rootzone_model import RootZone
from plant_engine.compute_transpiration import compute_transpiration


def test_recommend_irrigation_volume_basic():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    # After ET, projected volume below RAW so refill to full
    vol = recommend_irrigation_volume(zone, available_ml=120.0, expected_et_ml=40.0)
    assert vol == 80.0


def test_irrigation_no_action_when_sufficient():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    vol = recommend_irrigation_volume(zone, available_ml=150.0, expected_et_ml=30.0)
    assert vol == 0.0


def test_irrigation_clamped_to_capacity():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    # Projected requirement exceeds physical capacity
    vol = recommend_irrigation_volume(zone, available_ml=50.0, expected_et_ml=10.0)
    # Only 150 ml space remains
    assert vol == 150.0


def test_irrigation_volume_invalid_inputs():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    with pytest.raises(ValueError):
        recommend_irrigation_volume(zone, available_ml=-1.0, expected_et_ml=10.0)
    with pytest.raises(ValueError):
        recommend_irrigation_volume(zone, available_ml=50.0, expected_et_ml=-5.0)


def test_recommend_irrigation_interval():
    zone = RootZone(
        root_depth_cm=20,
        root_volume_cm3=2000,
        total_available_water_ml=400.0,
        readily_available_water_ml=200.0,
    )
    days = recommend_irrigation_interval(zone, available_ml=400.0, expected_et_ml_day=50.0)
    # (400 - 200)/50 = 4 days
    assert days == 4.0

    # When already below RAW, interval is zero
    assert recommend_irrigation_interval(zone, available_ml=150.0, expected_et_ml_day=50.0) == 0.0


def test_get_crop_coefficient():
    assert get_crop_coefficient("tomato", "vegetative") == 1.05
    assert get_crop_coefficient("unknown", "stage") == 1.0


def test_estimate_irrigation_demand():
    # ET0 5 mm/day, Kc 1.05 -> 5.25 mm/day * 2 m^2 = 10.5 L
    demand = estimate_irrigation_demand("tomato", "vegetative", 5.0, area_m2=2)
    assert demand == 10.5
    with pytest.raises(ValueError):
        estimate_irrigation_demand("tomato", "vegetative", -1.0)


def test_recommend_irrigation_from_environment():
    profile = {"kc": 1.2, "canopy_m2": 0.25}
    env = {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400}
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    result = recommend_irrigation_from_environment(profile, env, zone, 120.0)
    metrics = compute_transpiration(profile, env)
    expected = recommend_irrigation_volume(
        zone, available_ml=120.0, expected_et_ml=metrics["transpiration_ml_day"]
    )
    assert result["volume_ml"] == expected
    assert result["metrics"] == metrics


def test_daily_irrigation_target_lookup():
    assert get_daily_irrigation_target("citrus", "vegetative") == 250
    assert "citrus" in list_supported_plants()
    assert get_daily_irrigation_target("unknown", "stage") == 0.0


def test_generate_irrigation_schedule():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    schedule = generate_irrigation_schedule(zone, 150.0, [30.0, 30.0, 30.0])
    assert schedule == {1: 0.0, 2: 80.0, 3: 0.0}


def test_adjust_irrigation_for_efficiency():
    # Drip at 90% efficiency should scale volume up
    assert adjust_irrigation_for_efficiency(100.0, "drip") == 111.1
    # Unknown method returns original volume
    assert adjust_irrigation_for_efficiency(50.0, "unknown") == 50.0
    with pytest.raises(ValueError):
        adjust_irrigation_for_efficiency(-1.0, "drip")

