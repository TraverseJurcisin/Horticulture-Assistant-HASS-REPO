from datetime import date
from plant_engine.disease_monitor import (
    get_disease_thresholds,
    assess_disease_pressure,
    classify_disease_severity,
    recommend_threshold_actions,
    generate_disease_report,
    get_monitoring_interval,
    next_monitor_date,
)


def test_get_disease_thresholds():
    thresholds = get_disease_thresholds("citrus")
    assert thresholds["citrus_greening"] == 1
    assert thresholds["root_rot"] == 2


def test_assess_disease_pressure():
    obs = {"citrus greening": 2, "root rot": 1}
    result = assess_disease_pressure("citrus", obs)
    assert result == {"citrus_greening": True, "root_rot": False}


def test_classify_disease_severity():
    obs = {"citrus greening": 1, "root rot": 3}
    result = classify_disease_severity("citrus", obs)
    assert result["citrus_greening"] == "moderate"
    assert result["root_rot"] == "moderate"


def test_recommend_threshold_actions():
    obs = {"citrus greening": 2}
    actions = recommend_threshold_actions("citrus", obs)
    assert "citrus greening" in actions


def test_generate_disease_report():
    obs = {"citrus greening": 2, "root rot": 0}
    report = generate_disease_report("citrus", obs)
    assert report["severity"]["citrus_greening"] == "severe"
    assert report["thresholds_exceeded"]["citrus_greening"] is True
    assert "citrus greening" in report["treatments"]
    assert "root rot" in report["prevention"]


def test_get_monitoring_interval():
    assert get_monitoring_interval("citrus", "fruiting") == 4
    assert get_monitoring_interval("CITRUS") == 5
    assert get_monitoring_interval("unknown") is None


def test_next_monitor_date():
    last = date(2023, 1, 1)
    expected = date(2023, 1, 5)
    assert next_monitor_date("citrus", "fruiting", last) == expected
    assert next_monitor_date("unknown", None, last) is None
