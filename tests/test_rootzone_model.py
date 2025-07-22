from plant_engine.rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
    get_soil_parameters,
    RootZone,
)


def test_estimate_rootzone_depth():
    profile = {"max_root_depth_cm": 30}
    growth = {"vgi_total": 100}
    depth = estimate_rootzone_depth(profile, growth)
    assert 28 < depth <= 30


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


def test_estimate_water_capacity_texture():
    result = estimate_water_capacity(10, area_cm2=100, texture="loam")
    assert result.total_available_water_ml == 250.0
    assert result.mad_pct == 0.45

