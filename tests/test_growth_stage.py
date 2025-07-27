import pytest

from datetime import date
from plant_engine.growth_stage import (
    get_stage_info,
    get_stage_duration,
    estimate_stage_from_age,
    estimate_stage_from_date,
    stage_bounds,
    predict_harvest_date,
    get_total_cycle_duration,
    stage_progress,
    days_until_harvest,
    predict_next_stage_date,
    predict_stage_end_date,
    stage_progress_from_dates,
    get_germination_duration,
    days_until_next_stage,
    growth_stage_summary,
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


def test_estimate_stage_from_date():
    start = date(2025, 1, 1)
    cur = date(2025, 1, 15)
    assert estimate_stage_from_date("tomato", start, cur) == "seedling"

    with pytest.raises(ValueError):
        estimate_stage_from_date("tomato", cur, start)


def test_get_germination_duration():
    assert get_germination_duration("tomato") == 5
    assert get_germination_duration("lettuce") == 7
    assert get_germination_duration("unknown") is None


def test_days_until_next_stage():
    # stage duration for tomato seedling is 30 days
    assert days_until_next_stage("tomato", "seedling", 10) == 20
    # when elapsed exceeds duration the remaining time is zero
    assert days_until_next_stage("tomato", "seedling", 40) == 0
    assert days_until_next_stage("unknown", "seedling", 5) is None
    with pytest.raises(ValueError):
        days_until_next_stage("tomato", "seedling", -1)


def test_get_total_cycle_duration():
    assert get_total_cycle_duration("tomato") == 120
    assert get_total_cycle_duration("unknown") is None


def test_predict_stage_end_date():
    start = date(2025, 1, 1)
    end = predict_stage_end_date("tomato", "seedling", start)
    assert end == date(2025, 1, 31)
    assert predict_stage_end_date("unknown", "seedling", start) is None


def test_stage_progress_from_dates():
    start = date(2025, 1, 1)
    current = date(2025, 1, 16)
    progress = stage_progress_from_dates("tomato", "seedling", start, current)
    assert progress == 50.0

    with pytest.raises(ValueError):
        stage_progress_from_dates("tomato", "seedling", current, start)


def test_growth_stage_summary():
    start = date(2025, 1, 1)
    summary = growth_stage_summary("tomato", start)
    assert summary["total_cycle_days"] == 120
    assert summary["predicted_harvest_date"] == date(2025, 5, 1)
    stages = {item["stage"]: item["duration_days"] for item in summary["stages"]}
    assert stages["seedling"] == 30


def test_growth_stage_summary_unknown():
    result = growth_stage_summary("unknown")
    assert result["stages"] == []


def test_stage_bounds():
    bounds = stage_bounds("tomato")
    assert bounds[0] == ("seedling", 30)
    assert bounds[-1][1] == 120


