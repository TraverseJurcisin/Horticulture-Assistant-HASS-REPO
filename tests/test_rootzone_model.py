from plant_engine.rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
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

