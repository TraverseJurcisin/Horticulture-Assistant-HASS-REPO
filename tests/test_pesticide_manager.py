import datetime

from plant_engine.pesticide_manager import (
    get_withdrawal_days,
    earliest_harvest_date,
    adjust_harvest_date,
    calculate_harvest_window,
    get_reentry_hours,
    earliest_reentry_time,
    calculate_reentry_window,
    get_mode_of_action,
    list_known_pesticides,
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


def test_get_reentry_hours():
    assert get_reentry_hours("spinosad") == 4
    assert get_reentry_hours("imidacloprid") == 12
    assert get_reentry_hours("foo") is None


def test_earliest_reentry_time():
    dt = datetime.datetime(2024, 6, 1, 8, 0)
    result = earliest_reentry_time("spinosad", dt)
    assert result == dt + datetime.timedelta(hours=4)
    assert earliest_reentry_time("foo", dt) is None


def test_calculate_reentry_window():
    apps = [
        ("spinosad", datetime.datetime(2024, 6, 1, 6)),
        ("imidacloprid", datetime.datetime(2024, 6, 2, 9)),
    ]
    window = calculate_reentry_window(apps)
    expected = earliest_reentry_time("imidacloprid", apps[1][1])
    assert window == expected


def test_get_mode_of_action():
    assert get_mode_of_action("spinosad") == "spinosyn"
    assert get_mode_of_action("unknown") is None


def test_list_known_pesticides():
    pesticides = list_known_pesticides()
    assert "imidacloprid" in pesticides
    assert "pyrethrin" in pesticides

