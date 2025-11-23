import pytest

from ..engine.plant_engine.irrigation_manager import generate_infiltration_bursts


def test_generate_infiltration_bursts_basic():
    bursts = generate_infiltration_bursts(800, 0.1, "loam", max_hours=0.5)
    assert bursts == [400.0, 400.0]


def test_generate_infiltration_bursts_unknown_texture():
    bursts = generate_infiltration_bursts(800, 0.1, "unknown")
    assert bursts == [800.0]


def test_generate_infiltration_bursts_invalid_inputs():
    with pytest.raises(ValueError):
        generate_infiltration_bursts(500, 0.0, "loam")
    with pytest.raises(ValueError):
        generate_infiltration_bursts(500, 0.1, "loam", max_hours=0)
    assert generate_infiltration_bursts(0, 0.1, "loam") == []
