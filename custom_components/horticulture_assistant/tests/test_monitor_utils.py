from datetime import date

from plant_engine.monitor_utils import calculate_risk_score, generate_schedule, get_interval, next_date

DATA = {"citrus": {"fruiting": 4, "optimal": 5}, "tomato": {"seedling": 2}}


def test_get_interval():
    assert get_interval(DATA, "citrus", "fruiting") == 4
    assert get_interval(DATA, "citrus") == 5
    assert get_interval(DATA, "tomato", "flowering") is None


def test_next_date():
    last = date(2023, 1, 1)
    assert next_date(DATA, "citrus", "fruiting", last) == date(2023, 1, 5)
    assert next_date(DATA, "unknown", None, last) is None


def test_generate_schedule():
    start = date(2023, 1, 1)
    sched = generate_schedule(DATA, "citrus", "fruiting", start, 3)
    assert sched == [date(2023, 1, 5), date(2023, 1, 9), date(2023, 1, 13)]
    assert generate_schedule(DATA, "unknown", None, start, 2) == []


def test_calculate_risk_score():
    risks = {"a": "low", "b": "high", "c": "moderate"}
    score = calculate_risk_score(risks)
    assert 1.0 < score < 3.1
