import datetime

from plant_engine import phenology


def test_get_milestone_gdd_requirement():
    assert phenology.get_milestone_gdd_requirement("citrus", "flower_initiation") == 850


def test_get_milestone_photoperiod_requirement():
    assert phenology.get_milestone_photoperiod_requirement("citrus", "flower_initiation") == 12


def test_predict_milestone():
    assert phenology.predict_milestone("citrus", "flower_initiation", 900)
    assert not phenology.predict_milestone("citrus", "flower_initiation", 800)


def test_estimate_days_to_milestone():
    temps = [(20, 30)] * 60
    days = phenology.estimate_days_to_milestone("tomato", "fruiting_onset", temps)
    assert isinstance(days, int) and 0 < days <= 60


def test_estimate_milestone_date():
    temps = [(20, 30)] * 60
    start = datetime.date(2025, 1, 1)
    date = phenology.estimate_milestone_date("tomato", "fruiting_onset", start, temps)
    assert date is None or date >= start


def test_format_milestone_prediction():
    temps = [(20, 30)] * 80
    msg = phenology.format_milestone_prediction(
        "Buddha's Hand",
        "buddhas_hand",
        "flower_initiation",
        accumulated_gdd=870,
        temps=temps,
    )
    assert "Buddha's Hand" in msg
    assert "flower initiation" in msg
