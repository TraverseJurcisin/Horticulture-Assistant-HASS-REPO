from datetime import date
import pytest
from plant_engine.pest_monitor import (
    list_supported_plants,
    get_pest_thresholds,
    get_pest_threshold,
    is_threshold_exceeded,
    assess_pest_pressure,
    calculate_pest_pressure_index,
    recommend_threshold_actions,
    recommend_biological_controls,
    classify_pest_severity,
    generate_pest_report,
    get_monitoring_interval,
    next_monitor_date,
    generate_monitoring_schedule,
    generate_detailed_monitoring_schedule,
    risk_adjusted_monitor_interval,
    get_scouting_method,
    get_severity_thresholds,
    summarize_pest_management,
    calculate_pest_management_index,
    calculate_pest_management_index_series,
    calculate_severity_index,
    estimate_adjusted_pest_risk_series,
)


def test_get_pest_thresholds():
    thresh = get_pest_thresholds("citrus")
    assert thresh["aphids"] == 5

    # lookup should be case-insensitive
    thresh2 = get_pest_thresholds("CiTrUs")
    assert thresh2 == thresh

    stage_thresh = get_pest_thresholds("tomato", "seedling")
    assert stage_thresh["aphids"] == 5


def test_get_pest_threshold():
    assert get_pest_threshold("citrus", "aphids") == 5
    assert get_pest_threshold("citrus", "unknown") is None


def test_is_threshold_exceeded():
    assert is_threshold_exceeded("citrus", "aphids", 6) is True
    assert is_threshold_exceeded("citrus", "aphids", 4) is False
    assert is_threshold_exceeded("citrus", "unknown", 1) is None
    with pytest.raises(ValueError):
        is_threshold_exceeded("citrus", "aphids", -1)


def test_assess_pest_pressure():
    obs = {"aphids": 6, "scale": 1}
    result = assess_pest_pressure("CITRUS", obs)
    assert result["aphids"] is True
    assert result.get("scale") is False


def test_recommend_threshold_actions():
    obs = {"aphids": 6, "scale": 3}
    actions = recommend_threshold_actions("citrus", obs)
    assert "aphids" in actions
    assert "scale" in actions


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "citrus" in plants


def test_recommend_threshold_actions_case_insensitive():
    actions = recommend_threshold_actions("Citrus", {"APHIDS": 6})
    assert "aphids" in actions


def test_recommend_biological_controls():
    obs = {"aphids": 6, "scale": 3}
    bio = recommend_biological_controls("citrus", obs)
    assert "aphids" in bio
    assert isinstance(bio["aphids"], list)


def test_classify_pest_severity():
    obs = {"aphids": 3, "scale": 5}
    severity = classify_pest_severity("citrus", obs)
    assert severity["aphids"] == "low"
    assert severity["scale"] == "severe"


def test_classify_pest_severity_custom_thresholds(tmp_path, monkeypatch):
    override = tmp_path / "data"
    override.mkdir()
    path = override / "pest_severity_thresholds.json"
    path.write_text('{"aphids": {"moderate": 4, "severe": 8}}')

    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(override))
    from plant_engine import pest_monitor
    from plant_engine.utils import clear_dataset_cache, load_dataset

    clear_dataset_cache()
    pest_monitor._SEVERITY_THRESHOLDS = lambda: load_dataset(pest_monitor.SEVERITY_THRESHOLD_FILE)

    severity = pest_monitor.classify_pest_severity("citrus", {"aphids": 9})
    assert severity["aphids"] == "severe"

    monkeypatch.delenv("HORTICULTURE_OVERLAY_DIR")
    clear_dataset_cache()
    pest_monitor._SEVERITY_THRESHOLDS = lambda: load_dataset(pest_monitor.SEVERITY_THRESHOLD_FILE)


def test_get_severity_thresholds():
    thr = get_severity_thresholds("scale")
    assert thr["severe"] == 4


def test_negative_counts_raise():
    with pytest.raises(ValueError):
        assess_pest_pressure("citrus", {"aphids": -1})
    with pytest.raises(ValueError):
        classify_pest_severity("citrus", {"aphids": -2})


def test_calculate_pest_pressure_index():
    obs = {"aphids": 5, "scale": 1}
    idx = calculate_pest_pressure_index("citrus", obs)
    assert idx == 75.0


def test_generate_pest_report():
    obs = {"aphids": 6, "scale": 3}
    report = generate_pest_report("citrus", obs)
    assert report["severity"]["scale"] == "moderate" or report["severity"]["scale"] == "severe"
    assert report["thresholds_exceeded"]["aphids"] is True
    assert "aphids" in report["treatments"]
    assert "aphids" in report["beneficial_insects"]
    assert report["severity_actions"]["aphids"]


def test_get_monitoring_interval():
    assert get_monitoring_interval("citrus", "fruiting") == 3
    assert get_monitoring_interval("CITRUS") == 5
    assert get_monitoring_interval("unknown") is None


def test_next_monitor_date():
    last = date(2023, 1, 1)
    expected = date(2023, 1, 4)
    assert next_monitor_date("tomato", "fruiting", last) == expected
    assert next_monitor_date("unknown", None, last) is None


def test_generate_monitoring_schedule():
    start = date(2023, 1, 1)
    sched = generate_monitoring_schedule("tomato", "fruiting", start, 3)
    assert sched == [date(2023, 1, 4), date(2023, 1, 7), date(2023, 1, 10)]
    assert generate_monitoring_schedule("unknown", None, start, 2) == []


def test_risk_adjusted_monitor_interval_high():
    env = {"temperature": 26, "humidity": 80}
    interval = risk_adjusted_monitor_interval("citrus", "vegetative", env)
    assert interval == 2


def test_risk_adjusted_monitor_interval_moderate():
    env = {"temperature": 10, "humidity": 80}
    interval = risk_adjusted_monitor_interval("citrus", "vegetative", env)
    assert interval == 4


def test_risk_adjusted_monitor_interval_low():
    env = {"temperature": 10, "humidity": 55}
    interval = risk_adjusted_monitor_interval("citrus", "vegetative", env)
    assert interval == 5


def test_summarize_pest_management():
    obs = {"aphids": 6}
    env = {"temperature": 26, "humidity": 80}
    last = date(2023, 1, 1)
    summary = summarize_pest_management(
        "citrus",
        "vegetative",
        obs,
        environment=env,
        last_date=last,
    )
    assert summary["severity"]["aphids"] in {"moderate", "severe"}
    assert summary["risk"]["aphids"] == "high"
    assert summary.get("risk_score") is not None
    assert "next_monitor_date" in summary
    assert summary.get("severity_index") is not None


def test_get_scouting_method():
    method = get_scouting_method("mites")
    assert "paper" in method


def test_generate_detailed_monitoring_schedule():
    start = date(2023, 1, 1)
    plan = generate_detailed_monitoring_schedule("tomato", "fruiting", start, 2)
    assert len(plan) == 2
    entry = plan[0]
    assert entry["date"] == date(2023, 1, 4)
    assert "aphids" in entry["methods"]


def test_calculate_pest_management_index():
    obs = {"aphids": 6}
    env = {"temperature": 26, "humidity": 80}
    idx = calculate_pest_management_index("citrus", obs, env)
    assert idx == 60.0
    base = calculate_pest_pressure_index("citrus", obs)
    assert calculate_pest_management_index("citrus", obs) == base


def test_estimate_adjusted_pest_risk_series():
    series = [
        {"temperature": 26, "humidity": 80},
        {"temperature": 10, "humidity": 55},
    ]
    risk = estimate_adjusted_pest_risk_series("citrus", series)
    assert risk.get("aphids") == "high"
    assert risk.get("mites") == "moderate"


def test_calculate_pest_management_index_series():
    observations = [
        {"aphids": 6},
        {"aphids": 2},
    ]
    env_series = [
        {"temperature": 26, "humidity": 80},
        {"temperature": 10, "humidity": 55},
    ]
    idx = calculate_pest_management_index_series(
        "citrus", observations, env_series=env_series
    )
    assert idx > 0


def test_calculate_severity_index():
    severity = {"aphids": "moderate", "scale": "severe"}
    idx = calculate_severity_index(severity)
    assert idx == 2.5


def test_report_includes_severity_index():
    obs = {"aphids": 6}
    report = generate_pest_report("citrus", obs)
    assert report["severity_index"] > 0

