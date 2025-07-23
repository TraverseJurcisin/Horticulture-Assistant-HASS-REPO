from datetime import date

from plant_engine.integrated_monitor import generate_integrated_monitoring_schedule


def test_generate_integrated_monitoring_schedule():
    start = date(2023, 1, 1)
    sched = generate_integrated_monitoring_schedule("citrus", "fruiting", start, 4)
    assert sched == [
        date(2023, 1, 4),
        date(2023, 1, 5),
        date(2023, 1, 7),
        date(2023, 1, 9),
    ]


def test_generate_integrated_monitoring_schedule_unknown():
    start = date(2023, 1, 1)
    assert generate_integrated_monitoring_schedule("unknown", None, start, 3) == []
