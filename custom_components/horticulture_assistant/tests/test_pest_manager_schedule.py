from datetime import date

from ..engine.plant_engine.pest_manager import generate_cycle_monitoring_schedule


def test_generate_cycle_monitoring_schedule():
    start = date(2023, 1, 1)
    sched = generate_cycle_monitoring_schedule("tomato", start, ["aphids"])
    assert sched[0]["date"] == date(2023, 1, 8)
    assert sched[0]["stage"] == "seedling"
    assert sched[-1]["date"] == date(2023, 5, 1)
    assert sched[-1]["stage"] == "fruiting"
    assert len(sched) >= 20
