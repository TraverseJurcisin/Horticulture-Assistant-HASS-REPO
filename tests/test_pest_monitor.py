from plant_engine.pest_monitor import (
    list_supported_plants,
    get_pest_thresholds,
    assess_pest_pressure,
    recommend_threshold_actions,
    recommend_biological_controls,
    classify_pest_severity,
    generate_pest_report,
)


def test_get_pest_thresholds():
    thresh = get_pest_thresholds("citrus")
    assert thresh["aphids"] == 5

    # lookup should be case-insensitive
    thresh2 = get_pest_thresholds("CiTrUs")
    assert thresh2 == thresh


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


def test_generate_pest_report():
    obs = {"aphids": 6, "scale": 3}
    report = generate_pest_report("citrus", obs)
    assert report["severity"]["scale"] == "moderate" or report["severity"]["scale"] == "severe"
    assert report["thresholds_exceeded"]["aphids"] is True
    assert "aphids" in report["treatments"]
    assert "aphids" in report["beneficial_insects"]
