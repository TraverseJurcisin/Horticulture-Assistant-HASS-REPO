from datetime import date

from plant_engine.harvest_planner import build_stage_schedule


def test_build_stage_schedule():
    start = date(2025, 1, 1)
    schedule = build_stage_schedule("tomato", start)
    assert schedule[0]["stage"] == "seedling"
    assert schedule[0]["start_date"] == start
    assert schedule[-1]["stage"] == "fruiting"
    assert schedule[-1]["end_date"].isoformat() == "2025-05-01"
    # ensure durations sum to 120 days from dataset
    total = sum(entry["duration_days"] for entry in schedule)
    assert total == 120
