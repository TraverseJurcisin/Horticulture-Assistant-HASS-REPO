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
    get_rotation_interval,
    suggest_rotation_schedule,
    suggest_rotation_plan,
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


def test_get_rotation_interval():
    assert get_rotation_interval("imidacloprid") == 30
    assert get_rotation_interval("spinosad") == 10
    assert get_rotation_interval("unknown") is None


def test_suggest_rotation_schedule():
    start = datetime.date(2024, 1, 1)
    schedule = suggest_rotation_schedule("imidacloprid", start, 3)
    assert schedule == [
        datetime.date(2024, 1, 1),
        datetime.date(2024, 1, 31),
        datetime.date(2024, 3, 1),
    ]


def test_suggest_rotation_plan():
    start = datetime.date(2024, 1, 1)
    plan = suggest_rotation_plan(
        ["imidacloprid", "spinosad", "imidacloprid"], start
    )
    assert plan == [
        ("imidacloprid", start),
        ("spinosad", start + datetime.timedelta(days=30)),
        ("imidacloprid", start + datetime.timedelta(days=40)),
    ]


def test_get_phytotoxicity_risk():
    from plant_engine.pesticide_manager import get_phytotoxicity_risk

    assert get_phytotoxicity_risk("tomato", "copper_sulfate") == "high"
    assert get_phytotoxicity_risk("lettuce", "neem_oil") == "low"
    assert get_phytotoxicity_risk("tomato", "unknown") is None


def test_is_safe_for_crop():
    from plant_engine.pesticide_manager import is_safe_for_crop

    assert not is_safe_for_crop("tomato", "copper_sulfate")
    assert is_safe_for_crop("tomato", "neem_oil")


def test_check_mix_compatibility():
    from plant_engine.pesticide_manager import check_mix_compatibility, is_mix_compatible

    warnings = check_mix_compatibility(["copper_sulfate", "sulfur", "neem_oil"])
    assert ("copper_sulfate", "sulfur") in warnings
    assert warnings[("copper_sulfate", "sulfur")] == "reduced efficacy"
    assert ("neem_oil", "sulfur") in warnings or ("sulfur", "neem_oil") in warnings
    assert not is_mix_compatible(["copper_sulfate", "sulfur"])


