from plant_engine.nutrient_manager import recommend_ratio_adjustments


def test_recommend_ratio_adjustments():
    current = {"N": 60, "P": 20, "K": 20}
    result = recommend_ratio_adjustments(current, "citrus", "vegetative", tolerance=0.01)
    # Sum is 100, target ratio ~N0.43 P0.22 K0.35
    assert result["N"] < 0  # need to decrease N
    assert result["K"] > 0  # need to increase K
    assert round(result["P"], 2) > 0
