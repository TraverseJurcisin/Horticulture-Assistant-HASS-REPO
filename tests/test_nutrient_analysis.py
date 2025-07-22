from plant_engine.nutrient_analysis import analyze_nutrient_profile


def test_analyze_nutrient_profile():
    current = {"N": 50, "P": 10, "K": 40, "Fe": 0.5}
    result = analyze_nutrient_profile(current, "lettuce", "seedling")
    assert "recommended" in result
    assert "deficiencies" in result
    assert "surplus" in result
    assert "balance" in result
    assert "interaction_warnings" in result
    assert result["deficiencies"]
    assert not result["interaction_warnings"]
