from plant_engine.tissue_analysis import get_target_ranges, evaluate_tissue_levels


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
