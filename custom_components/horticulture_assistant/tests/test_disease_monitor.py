from datetime import date

from plant_engine.disease_monitor import (
    adjust_risk_with_resistance,
    assess_disease_pressure,
    classify_disease_severity,
    estimate_adjusted_disease_risk,
    generate_detailed_monitoring_schedule,
    generate_disease_report,
    generate_monitoring_schedule,
    get_disease_thresholds,
    get_monitoring_interval,
    get_scouting_method,
    get_severity_action,
    next_monitor_date,
    recommend_threshold_actions,
    risk_adjusted_monitor_interval,
    summarize_disease_management,
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


def test_generate_monitoring_schedule():
    start = date(2023, 1, 1)
    sched = generate_monitoring_schedule("citrus", "fruiting", start, 2)
    assert sched == [date(2023, 1, 5), date(2023, 1, 9)]
    assert generate_monitoring_schedule("unknown", None, start, 1) == []


def test_get_severity_action():
    assert get_severity_action("low").startswith("Monitor")
    assert get_severity_action("moderate")
    assert get_severity_action("unknown") == ""


def test_report_includes_severity_actions():
    obs = {"citrus greening": 3}
    report = generate_disease_report("citrus", obs)
    assert report["severity_actions"]["citrus_greening"]


def test_adjust_risk_with_resistance():
    risks = {"greasy_spot": "high", "powdery_mildew": "moderate"}
    adjusted = adjust_risk_with_resistance("citrus", risks)
    assert adjusted["greasy_spot"] == "moderate"
    assert adjusted["powdery_mildew"] == "moderate"


def test_estimate_adjusted_disease_risk():
    env = {"humidity_pct": 80, "temp_c": 25}
    risk = estimate_adjusted_disease_risk("citrus", env)
    assert risk["greasy_spot"] == "moderate"
    assert risk["powdery_mildew"] == "high"


def test_risk_adjusted_monitor_interval():
    env = {"humidity_pct": 80, "temp_c": 25}
    interval = risk_adjusted_monitor_interval("citrus", "fruiting", env)
    assert interval == 2


def test_summarize_disease_management():
    obs = {"citrus greening": 2}
    env = {"humidity_pct": 85, "temp_c": 26}
    last = date(2023, 1, 1)
    summary = summarize_disease_management(
        "citrus",
        "fruiting",
        obs,
        environment=env,
        last_date=last,
    )
    assert summary["severity"]["citrus_greening"] in {"moderate", "severe"}
    assert summary["risk"]["greasy_spot"] in {"low", "moderate", "high"}
    assert summary.get("risk_score") is not None
    assert "next_monitor_date" in summary


def test_get_scouting_method():
    method = get_scouting_method("powdery mildew")
    assert "powdery" in method.lower()


def test_generate_detailed_monitoring_schedule():
    start = date(2023, 1, 1)
    plan = generate_detailed_monitoring_schedule("citrus", "fruiting", start, 2)
    assert len(plan) == 2
    entry = plan[0]
    assert entry["date"] == date(2023, 1, 5)
    assert "citrus greening" in entry["methods"]
