from plant_engine.tissue_analysis import (
    get_target_ranges,
    evaluate_tissue_levels,
    score_tissue_levels,
)


def test_get_target_ranges_known():
    ranges = get_target_ranges("citrus", "vegetative")
    assert ranges["N"] == [2.5, 3.0]


def test_get_target_ranges_unknown():
    assert get_target_ranges("foo", "bar") == {}


def test_evaluate_tissue_levels():
    levels = {"N": 2.2, "P": 0.15, "K": 1.5}
    result = evaluate_tissue_levels("citrus", "vegetative", levels)
    assert result["N"] == "low"
    assert result["P"] == "ok"
    assert result["K"] == "ok"


def test_score_tissue_levels_perfect():
    levels = {"N": 2.7, "P": 0.15, "K": 1.5}
    score = score_tissue_levels("citrus", "vegetative", levels)
    assert score == 100.0


def test_score_tissue_levels_low_high():
    levels = {"N": 2.0, "P": 0.25, "K": 3.0}
    # N below range, K above range
    score = score_tissue_levels("tomato", "vegetative", levels)
    assert 0 < score < 100
