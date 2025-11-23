from ..engine.plant_engine.canopy import estimate_canopy_area, get_canopy_area


def test_get_canopy_area_known():
    assert get_canopy_area("lettuce", "vegetative") == 0.1


def test_get_canopy_area_unknown():
    assert get_canopy_area("unknown") is None


def test_estimate_canopy_area_dataset():
    assert estimate_canopy_area("strawberry", "flowering") == 0.25


def test_estimate_canopy_area_spacing_fallback():
    # lettuce spacing is 25 cm -> area ~0.0625 m^2
    val = estimate_canopy_area("lettuce", stage=None)
    assert round(val, 3) == 0.062


def test_estimate_canopy_area_default():
    assert estimate_canopy_area("unknown") == 0.25
