import pytest

from datetime import date
from plant_engine.growth_stage import (
    get_stage_info,
    get_stage_duration,
    estimate_stage_from_age,
    predict_harvest_date,
    stage_progress,
    days_until_harvest,
    predict_next_stage_date,
)


def test_get_stage_info():
    info = get_stage_info("tomato", "flowering")
    assert info["duration_days"] == 20


def test_get_stage_info_case_insensitive():
    info = get_stage_info("ToMaTo", "FlOwErInG")
    assert info["duration_days"] == 20


def test_get_stage_duration():
    assert get_stage_duration("tomato", "flowering") == 20
    assert get_stage_duration("tomato", "unknown") is None


def test_get_stage_duration_case_insensitive():
    assert get_stage_duration("ToMaTo", "FlOwErInG") == 20


def test_estimate_stage_from_age():
    assert estimate_stage_from_age("tomato", 5) == "seedling"
    assert estimate_stage_from_age("tomato", 45) == "vegetative"
    assert estimate_stage_from_age("tomato", 150) is None


def test_estimate_stage_from_age_case_insensitive():
    assert estimate_stage_from_age("ToMaTo", 5) == "seedling"


def test_estimate_stage_from_age_negative():
    with pytest.raises(ValueError):
        estimate_stage_from_age("tomato", -1)


def test_predict_harvest_date():
    start = date(2025, 1, 1)
    expected = date(2025, 5, 1)  # 120 days from dataset
    assert predict_harvest_date("tomato", start) == expected

    assert predict_harvest_date("unknown", start) is None


def test_stage_progress():
    assert stage_progress("tomato", "seedling", 5) == 16.7
    assert stage_progress("tomato", "seedling", 30) == 100.0
    assert stage_progress("tomato", "unknown", 10) is None
    with pytest.raises(ValueError):
        stage_progress("tomato", "seedling", -1)


def test_days_until_harvest():
    start = date(2025, 1, 1)
    today = date(2025, 2, 1)
    assert days_until_harvest("tomato", start, today) == 89
    assert days_until_harvest("unknown", start, today) is None


def test_predict_next_stage_date():
    stage_start = date(2025, 1, 1)
    next_date = predict_next_stage_date("tomato", "seedling", stage_start)
    assert next_date == date(2025, 1, 31)

    assert (
        predict_next_stage_date("unknown", "seedling", stage_start) is None
    )

