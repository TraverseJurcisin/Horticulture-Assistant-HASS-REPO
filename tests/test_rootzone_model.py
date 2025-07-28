from plant_engine.rootzone_model import (
    estimate_rootzone_depth,
    get_default_root_depth,
    estimate_water_capacity,
    calculate_remaining_water,
    get_soil_parameters,
    soil_moisture_pct,
    get_infiltration_rate,
    estimate_infiltration_time,
    calculate_infiltration_volume,
    RootZone,
)
import pytest


def test_estimate_rootzone_depth():
    profile = {"max_root_depth_cm": 30}
    growth = {"vgi_total": 100}
    depth = estimate_rootzone_depth(profile, growth)
    assert 28 < depth <= 30


def test_estimate_rootzone_depth_custom_params(monkeypatch):
    import plant_engine.rootzone_model as rz
    monkeypatch.setattr(
        rz,
        "_GROWTH_PARAMS",
        {"tomato": {"midpoint": 70, "k": 0.05}},
        raising=False,
    )

    profile = {"plant_type": "tomato"}
    depth = rz.estimate_rootzone_depth(profile, {"vgi_total": 100})
    assert 48 < depth < 50


def test_estimate_water_capacity():
    result = estimate_water_capacity(20, area_cm2=100)
    assert isinstance(result, RootZone)
    assert result.total_available_water_ml == 400.0
    assert result.readily_available_water_ml == 200.0


def test_estimate_water_capacity_custom():
    result = estimate_water_capacity(
        10,
        area_cm2=100,
        field_capacity=0.30,
        mad_fraction=0.4,
    )
    assert result.total_available_water_ml == 300.0
    assert result.readily_available_water_ml == 120.0
    assert result.field_capacity_pct == 0.30
    assert result.mad_pct == 0.4


def test_get_soil_parameters():
    params = get_soil_parameters("loam")
    assert params["field_capacity"] == 0.25
    assert params["mad_fraction"] == 0.45
    assert params["infiltration_rate_mm_hr"] == 10


def test_get_default_root_depth():
    assert get_default_root_depth("tomato") == 60
    assert get_default_root_depth("unknown") == 30.0


def test_estimate_water_capacity_texture():
    result = estimate_water_capacity(10, area_cm2=100, texture="loam")
    assert result.total_available_water_ml == 250.0
    assert result.mad_pct == 0.45


def test_calculate_remaining_water():
    rz = estimate_water_capacity(10, area_cm2=100)
    remaining = calculate_remaining_water(rz, 150.0, irrigation_ml=50.0, et_ml=25.0)
    assert remaining == 175.0


def test_calculate_remaining_water_clamped():
    rz = estimate_water_capacity(10, area_cm2=100)
    remaining = calculate_remaining_water(rz, 400.0, irrigation_ml=50.0, et_ml=10.0)
    assert remaining == rz.total_available_water_ml


def test_calculate_remaining_water_negative():
    rz = estimate_water_capacity(10, area_cm2=100)
    with pytest.raises(ValueError):
        calculate_remaining_water(rz, -1.0)


def test_soil_moisture_pct():
    rz = estimate_water_capacity(10, area_cm2=100)
    assert soil_moisture_pct(rz, 100.0) == 50.0
    with pytest.raises(ValueError):
        soil_moisture_pct(rz, -1)


def test_rootzone_methods():
    rz = estimate_water_capacity(10, area_cm2=100)
    new = rz.calculate_remaining_water(100.0, irrigation_ml=50.0, et_ml=25.0)
    assert new == 125.0
    assert rz.moisture_pct(new) == soil_moisture_pct(rz, new)


def test_get_infiltration_rate():
    rate = get_infiltration_rate("loam")
    assert rate == 10
    assert get_infiltration_rate("unknown") is None


def test_estimate_infiltration_time():
    hours = estimate_infiltration_time(1000, 1.0, "loam")
    assert hours == 0.1
    assert estimate_infiltration_time(1000, 1.0, "unknown") is None
    with pytest.raises(ValueError):
        estimate_infiltration_time(-1, 1.0, "loam")

    # custom rate overrides dataset lookup
    assert estimate_infiltration_time(1000, 1.0, infiltration_rate=5) == 0.2


def test_calculate_infiltration_volume():
    vol = calculate_infiltration_volume(0.2, 1.0, "loam")
    assert vol == 2000.0
    assert calculate_infiltration_volume(0.2, 1.0, "unknown") is None
    with pytest.raises(ValueError):
        calculate_infiltration_volume(-1, 1.0, "loam")

    # custom rate overrides dataset lookup
    assert calculate_infiltration_volume(0.2, 1.0, infiltration_rate=5) == 1000.0

