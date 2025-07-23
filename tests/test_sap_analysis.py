from plant_engine.sap_analysis import (
    get_sap_targets,
    evaluate_sap_levels,
    score_sap_levels,
)


def test_get_sap_targets_known():
    ranges = get_sap_targets("citrus", "vegetative")
    assert ranges["N"] == [300, 600]


def test_get_sap_targets_unknown():
    assert get_sap_targets("foo", "bar") == {}


def test_evaluate_sap_levels():
    levels = {"N": 280, "P": 25, "K": 350}
    result = evaluate_sap_levels("citrus", "vegetative", levels)
    assert result["N"] == "low"
    assert result["P"] == "ok"
    assert result["K"] == "ok"


def test_score_sap_levels_perfect():
    levels = {"N": 500, "P": 50, "K": 500}
    assert score_sap_levels("tomato", "vegetative", levels) == 100.0


def test_score_sap_levels_mixed():
    levels = {"N": 800, "P": 20, "K": 350}
    score = score_sap_levels("tomato", "vegetative", levels)
    assert 0 < score < 100
