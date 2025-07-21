import pytest

from plant_engine.growth_stage import (
    get_stage_info,
    get_stage_duration,
    estimate_stage_from_age,
)


def test_get_stage_info():
    info = get_stage_info("tomato", "flowering")
    assert info["duration_days"] == 20


def test_get_stage_duration():
    assert get_stage_duration("tomato", "flowering") == 20
    assert get_stage_duration("tomato", "unknown") is None


def test_estimate_stage_from_age():
    assert estimate_stage_from_age("tomato", 5) == "seedling"
    assert estimate_stage_from_age("tomato", 45) == "vegetative"
    assert estimate_stage_from_age("tomato", 150) is None


def test_estimate_stage_from_age_negative():
    with pytest.raises(ValueError):
        estimate_stage_from_age("tomato", -1)
