import pytest

from ..engine.plant_engine.et_model import get_reference_et0
from ..engine.plant_engine.irrigation_manager import estimate_irrigation_from_month


def test_get_reference_et0():
    assert get_reference_et0(1) == 2.0
    assert get_reference_et0(7) == 6.5
    with pytest.raises(ValueError):
        get_reference_et0(13)


def test_estimate_irrigation_from_month():
    vol = estimate_irrigation_from_month("citrus", "vegetative", 5, area_m2=0.5)
    assert vol > 0
