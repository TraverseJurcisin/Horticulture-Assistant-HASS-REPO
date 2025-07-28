import pytest

from plant_engine.et_model import get_zone_reference_et0
from plant_engine.irrigation_manager import estimate_irrigation_from_zone_month


def test_get_zone_reference_et0():
    assert get_zone_reference_et0("temperate", 1) == 2.0
    assert get_zone_reference_et0("arid", 7) == 8.0
    with pytest.raises(ValueError):
        get_zone_reference_et0("temperate", 13)


def test_estimate_irrigation_from_zone_month():
    vol = estimate_irrigation_from_zone_month("citrus", "vegetative", "temperate", 5, area_m2=0.5)
    assert vol > 0
