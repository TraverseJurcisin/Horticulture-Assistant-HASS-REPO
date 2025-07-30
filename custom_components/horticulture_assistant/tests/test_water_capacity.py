import pytest
from plant_engine import water_capacity


def test_get_capacity():
    assert water_capacity.get_capacity("loam") == 60
    assert water_capacity.get_capacity("unknown") == 0.0


def test_estimate_storage():
    assert water_capacity.estimate_storage("loam", 30) == 60
    assert water_capacity.estimate_storage("loam", 15) == 30
    with pytest.raises(ValueError):
        water_capacity.estimate_storage("loam", -1)
