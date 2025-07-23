import datetime

from plant_engine.pesticide_manager import get_withdrawal_days, earliest_harvest_date


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
