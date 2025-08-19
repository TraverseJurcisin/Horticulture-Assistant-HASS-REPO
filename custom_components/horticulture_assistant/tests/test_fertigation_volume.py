import pytest
from plant_engine.fertigation import (
    get_fertigation_volume,
    estimate_fertigation_solution_volume,
)


def test_get_fertigation_volume():
    assert get_fertigation_volume("tomato", "vegetative") == 250
    assert get_fertigation_volume("lettuce", "harvest") == 120
    assert get_fertigation_volume("unknown", "stage") is None


def test_estimate_fertigation_solution_volume():
    vol = estimate_fertigation_solution_volume(4, "tomato", "fruiting")
    assert vol == 1.2
    assert estimate_fertigation_solution_volume(1, "unknown", "stage") is None
    with pytest.raises(ValueError):
        estimate_fertigation_solution_volume(0, "tomato", "vegetative")
