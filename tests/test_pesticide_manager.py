import datetime

from plant_engine.pesticide_manager import (
    get_withdrawal_days,
    earliest_harvest_date,
    adjust_harvest_date,
    calculate_harvest_window,
)


def test_get_withdrawal_days_known():
    assert get_withdrawal_days("spinosad") == 1
    assert get_withdrawal_days("imidacloprid") == 7


def test_get_withdrawal_days_unknown():
    assert get_withdrawal_days("foo") is None


def test_earliest_harvest_date():
    date = datetime.date(2024, 6, 1)
    harvest = earliest_harvest_date("spinosad", date)
    assert harvest == date + datetime.timedelta(days=1)
    assert earliest_harvest_date("foo", date) is None


def test_adjust_harvest_date():
    start = datetime.date(2024, 5, 1)
    application = datetime.date(2024, 7, 29)
    adjusted = adjust_harvest_date("lettuce", start, "imidacloprid", application)
    expected = earliest_harvest_date("imidacloprid", application)
    assert adjusted == expected


def test_calculate_harvest_window():
    applications = [
        ("spinosad", datetime.date(2024, 6, 1)),
        ("imidacloprid", datetime.date(2024, 6, 10)),
    ]
    harvest = calculate_harvest_window(applications)
    expected = earliest_harvest_date("imidacloprid", datetime.date(2024, 6, 10))
    assert harvest == expected

