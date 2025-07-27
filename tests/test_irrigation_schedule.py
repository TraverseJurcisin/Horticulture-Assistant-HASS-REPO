from custom_components.horticulture_assistant.utils.irrigation_schedule import (
    parse_schedule,
)


def test_parse_schedule_basic():
    data = {
        "method": "time_pattern",
        "time": "06:00",
        "duration_min": 15,
    }
    sched = parse_schedule(data)
    assert sched.method == "time_pattern"
    assert sched.time == "06:00"
    assert sched.duration_min == 15
    assert sched.volume_l is None
    assert sched.pulses is None


def test_parse_schedule_pulsed():
    data = {
        "method": "pulsed",
        "pulses": {"p1": ["08:00", "08:30"], "p2": ["12:00"]},
    }
    sched = parse_schedule(data)
    assert sched.pulses == {"p1": ["08:00", "08:30"], "p2": ["12:00"]}

