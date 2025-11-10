import pytest

from plant_engine.compute_transpiration import compute_transpiration
from plant_engine.irrigation_manager import (
    IrrigationRecommendation,
    adjust_irrigation_for_efficiency,
    adjust_irrigation_for_zone,
    estimate_irrigation_demand,
    estimate_irrigation_time,
    generate_cycle_infiltration_schedule,
    generate_cycle_irrigation_plan,
    generate_env_irrigation_schedule,
    generate_env_precipitation_schedule,
    generate_irrigation_schedule,
    generate_irrigation_schedule_with_runtime,
    generate_precipitation_schedule,
    get_crop_coefficient,
    get_daily_irrigation_target,
    get_irrigation_zone_modifier,
    get_rain_capture_efficiency,
    get_recommended_interval,
    list_supported_plants,
    recommend_irrigation_from_environment,
    recommend_irrigation_interval,
    recommend_irrigation_volume,
    recommend_irrigation_with_rainfall,
    summarize_irrigation_schedule,
)
from plant_engine.rootzone_model import RootZone, calculate_remaining_water
from plant_engine.utils import clear_dataset_cache


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


def test_recommend_irrigation_with_rainfall():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    result = recommend_irrigation_with_rainfall(
        zone,
        available_ml=120.0,
        expected_et_ml=40.0,
        rainfall_ml=10.0,
    )
    expected = recommend_irrigation_volume(zone, 120.0, expected_et_ml=31.0)
    assert result == expected

    with pytest.raises(ValueError):
        recommend_irrigation_with_rainfall(zone, 120.0, expected_et_ml=40.0, rainfall_ml=-5.0)


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
    expected = recommend_irrigation_volume(zone, available_ml=120.0, expected_et_ml=metrics["transpiration_ml_day"])
    assert result["volume_ml"] == expected
    assert result["metrics"] == metrics


def test_irrigation_recommendation_dataclass():
    metrics = {"et0_mm_day": 5.0, "eta_mm_day": 6.0, "transpiration_ml_day": 500.0}
    rec = IrrigationRecommendation(100.0, metrics)
    assert rec.as_dict() == {"volume_ml": 100.0, "metrics": metrics}


def test_daily_irrigation_target_lookup():
    assert get_daily_irrigation_target("citrus", "vegetative") == 250
    assert "citrus" in list_supported_plants()
    assert get_daily_irrigation_target("unknown", "stage") == 0.0


def test_daily_irrigation_target_blueberry():
    assert get_daily_irrigation_target("blueberry", "vegetative") == 200
    assert get_recommended_interval("blueberry", "vegetative") == 2


def test_get_recommended_interval():
    assert get_recommended_interval("citrus", "seedling") == 2
    # When a stage-specific interval isn't defined the value falls back to
    # drought tolerance data for the crop.
    assert get_recommended_interval("citrus", "unknown") == 3


def test_generate_irrigation_schedule():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    schedule = generate_irrigation_schedule(zone, 150.0, [30.0, 30.0, 30.0])
    assert schedule == {1: 0.0, 2: 80.0, 3: 0.0}


def test_generate_irrigation_schedule_with_method():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    schedule = generate_irrigation_schedule(zone, 150.0, [30.0, 30.0, 30.0], method="drip")
    assert schedule[1] == 0.0
    assert schedule[2] == pytest.approx(88.9, rel=1e-2)


def test_adjust_irrigation_for_efficiency():
    # Drip at 90% efficiency should scale volume up
    assert adjust_irrigation_for_efficiency(100.0, "drip") == 111.1
    # Unknown method returns original volume
    assert adjust_irrigation_for_efficiency(50.0, "unknown") == 50.0
    with pytest.raises(ValueError):
        adjust_irrigation_for_efficiency(-1.0, "drip")


def test_generate_env_irrigation_schedule():
    profile = {"kc": 1.0, "canopy_m2": 0.25}
    env = {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400}
    env_series = [env, env]
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )

    sched = generate_env_irrigation_schedule(profile, env_series, zone, 150.0)

    m1 = compute_transpiration(profile, env)
    vol1 = recommend_irrigation_volume(zone, 150.0, m1["transpiration_ml_day"])
    remaining = calculate_remaining_water(zone, 150.0, irrigation_ml=vol1, et_ml=m1["transpiration_ml_day"])
    m2 = compute_transpiration(profile, env)
    vol2 = recommend_irrigation_volume(zone, remaining, m2["transpiration_ml_day"])

    assert sched[1]["volume_ml"] == vol1
    assert sched[1]["metrics"] == m1
    assert sched[2]["volume_ml"] == vol2
    assert sched[2]["metrics"] == m2


def test_generate_precipitation_schedule():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    schedule = generate_precipitation_schedule(
        zone,
        150.0,
        [30.0, 30.0, 30.0],
        [10.0, 0.0, 20.0],
        surface="mulch",
    )
    # First day net ET = 30 - 10*0.75 = 22.5 -> no irrigation needed
    assert schedule[1] == 0.0
    # Second day no rain -> irrigation required
    assert schedule[2] > 0.0


def test_estimate_irrigation_time():
    # 4 L/h emitter with 2 emitters -> 8 L/h -> 8000 mL/h
    hrs = estimate_irrigation_time(4000, "drip", emitters=2)
    assert hrs == 0.5
    # unknown emitter returns 0.0
    assert estimate_irrigation_time(1000, "unknown") == 0.0
    with pytest.raises(ValueError):
        estimate_irrigation_time(-1, "drip")
    with pytest.raises(ValueError):
        estimate_irrigation_time(1000, "drip", emitters=0)


def test_generate_irrigation_schedule_with_runtime():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    schedule = generate_irrigation_schedule_with_runtime(
        zone,
        150.0,
        [30.0, 30.0],
        emitter_type="drip",
        emitters=2,
    )
    assert schedule[1]["volume_ml"] == 0.0
    runtime = estimate_irrigation_time(80.0, "drip", emitters=2)
    assert schedule[2]["runtime_h"] == pytest.approx(runtime, rel=1e-2)


def test_summarize_irrigation_schedule():
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    schedule = generate_irrigation_schedule_with_runtime(
        zone,
        150.0,
        [30.0, 30.0],
        emitter_type="drip",
        emitters=2,
    )
    summary = summarize_irrigation_schedule(schedule)
    assert summary["events"] == 1
    assert summary["total_volume_ml"] > 0
    assert summary["total_runtime_h"] > 0


def test_generate_cycle_irrigation_plan():
    plan = generate_cycle_irrigation_plan("lettuce")
    assert "vegetative" in plan
    veg = plan["vegetative"]
    # verify at least one scheduled volume and it is positive
    assert veg
    assert veg[1] > 0


def test_generate_env_precipitation_schedule():
    profile = {"kc": 1.0, "canopy_m2": 0.25}
    env = {"temp_c": 25, "rh_pct": 50, "par_w_m2": 400}
    env_series = [env, env]
    rain = [10.0, 0.0]
    zone = RootZone(
        root_depth_cm=10,
        root_volume_cm3=1000,
        total_available_water_ml=200.0,
        readily_available_water_ml=100.0,
    )
    schedule = generate_env_precipitation_schedule(
        profile,
        env_series,
        rain,
        zone,
        150.0,
        surface="mulch",
    )

    metrics = compute_transpiration(profile, env)
    rain_eff = get_rain_capture_efficiency("mulch")
    net_et1 = max(0.0, metrics["transpiration_ml_day"] - rain[0] * rain_eff)
    vol1 = recommend_irrigation_volume(zone, 150.0, net_et1)
    remaining = calculate_remaining_water(zone, 150.0, irrigation_ml=vol1, et_ml=net_et1)
    net_et2 = max(0.0, metrics["transpiration_ml_day"] - rain[1] * rain_eff)
    vol2 = recommend_irrigation_volume(zone, remaining, net_et2)

    assert schedule[1]["volume_ml"] == vol1
    assert schedule[1]["metrics"] == metrics
    assert schedule[2]["volume_ml"] == vol2


def test_irrigation_zone_modifier():
    assert get_irrigation_zone_modifier("arid") == 1.2
    assert get_irrigation_zone_modifier("unknown") == 1.0


def test_adjust_irrigation_for_zone():
    assert adjust_irrigation_for_zone(100.0, "arid") == 120.0
    assert adjust_irrigation_for_zone(50.0, "humid") == 40.0
    with pytest.raises(ValueError):
        adjust_irrigation_for_zone(-1.0, "arid")


def test_generate_cycle_infiltration_schedule():
    schedule = generate_cycle_infiltration_schedule("lettuce", 0.1, "clay")
    veg = schedule["vegetative"]
    assert veg[1] == [150.0, 150.0]


def test_lazy_dataset_loading():
    clear_dataset_cache()
    plants = list_supported_plants()
    assert "lettuce" in plants
