from datetime import date

from plant_engine.harvest_window import get_harvest_window, is_harvest_time


def test_get_harvest_window():
    window = get_harvest_window("tomato")
    assert window == (60, 90)


def test_is_harvest_time_true():
    start = date(2024, 5, 1)
    current = date(2024, 6, 30)
    assert is_harvest_time("tomato", start, current)


def test_is_harvest_time_false():
    start = date(2024, 5, 1)
    current = date(2024, 5, 15)
    assert not is_harvest_time("tomato", start, current)
