import datetime

import pytest
from plant_engine.pesticide_manager import (
    adjust_harvest_date,
    calculate_harvest_window,
    calculate_reentry_window,
    earliest_harvest_date,
    earliest_reentry_time,
    estimate_application_cost,
    estimate_rotation_plan_cost,
    get_mode_of_action,
    get_pesticide_price,
    get_reentry_hours,
    get_rotation_interval,
    get_withdrawal_days,
    list_known_pesticides,
    next_rotation_date,
    suggest_pest_rotation_plan,
    suggest_rotation_plan,
    suggest_rotation_schedule,
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


def test_next_rotation_date():
    last = datetime.date(2024, 6, 1)
    result = next_rotation_date("spinosad", last)
    assert result == last + datetime.timedelta(days=10)
    assert next_rotation_date("unknown", last) is None


def test_suggest_rotation_plan():
    start = datetime.date(2024, 1, 1)
    plan = suggest_rotation_plan(["imidacloprid", "spinosad", "imidacloprid"], start)
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


def test_get_application_rate():
    from plant_engine.pesticide_manager import get_application_rate

    assert get_application_rate("neem_oil") == 5.0
    assert get_application_rate("unknown") is None


def test_calculate_application_amount():
    from plant_engine.pesticide_manager import calculate_application_amount

    amount = calculate_application_amount("neem_oil", 2.0)
    assert amount == 10.0

    with pytest.raises(ValueError):
        calculate_application_amount("neem_oil", 0)
    with pytest.raises(KeyError):
        calculate_application_amount("unknown", 1.0)


def test_summarize_pesticide_restrictions():
    from plant_engine.pesticide_manager import (
        earliest_harvest_date,
        earliest_reentry_time,
        summarize_pesticide_restrictions,
    )

    apps = [
        ("spinosad", datetime.datetime(2024, 6, 1, 8)),
        ("imidacloprid", datetime.datetime(2024, 6, 2, 9)),
    ]
    summary = summarize_pesticide_restrictions(apps)
    assert summary["reentry_time"] == earliest_reentry_time("imidacloprid", apps[1][1])
    assert summary["harvest_date"] == earliest_harvest_date("imidacloprid", apps[1][1].date())


def test_get_pesticide_price_and_cost():
    assert get_pesticide_price("neem_oil") == 15.0
    cost = estimate_application_cost("neem_oil", 2.0)
    assert cost == 0.15


def test_active_ingredient_info():
    from plant_engine.pesticide_manager import get_active_ingredient_info, list_active_ingredients

    info = get_active_ingredient_info("spinosad")
    assert info["class"] == "spinosyn"
    assert "mode_of_action" in info

    ingredients = list_active_ingredients()
    assert "imidacloprid" in ingredients


def test_pesticide_efficacy_helpers():
    from plant_engine.pesticide_manager import get_pesticide_efficacy, list_effective_pesticides

    assert get_pesticide_efficacy("imidacloprid", "aphids") == 5
    assert get_pesticide_efficacy("pyrethrin", "spider mites") == 2
    assert get_pesticide_efficacy("unknown", "aphids") is None

    ranking = list_effective_pesticides("aphids")
    assert ranking[0][0] == "imidacloprid"
    assert ranking[0][1] >= ranking[-1][1]


def test_estimate_rotation_plan_cost():
    import importlib

    import plant_engine.utils as utils
    from plant_engine import nutrient_manager as nm

    utils.clear_dataset_cache()
    importlib.reload(nm)

    start = datetime.date(2024, 1, 1)
    plan = suggest_rotation_plan(["spinosad", "neem_oil"], start)
    expected = estimate_application_cost("spinosad", 2.0) + estimate_application_cost("neem_oil", 2.0)
    cost = estimate_rotation_plan_cost(plan, 2.0)
    assert cost == expected

    with pytest.raises(ValueError):
        estimate_rotation_plan_cost(plan, 0)


def test_suggest_pest_rotation_plan():
    start = datetime.date(2024, 1, 1)
    plan = suggest_pest_rotation_plan("aphids", start, 3)
    assert plan[0][0] in {"imidacloprid", "spinosad", "pyrethrin"}
    assert len(plan) == 3
    # ensure intervals follow product guidelines
    assert plan[1][1] > plan[0][1]
