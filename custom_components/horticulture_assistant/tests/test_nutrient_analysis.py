from plant_engine.nutrient_analysis import NutrientAnalysis, analyze_nutrient_profile


def test_analyze_nutrient_profile():
    current = {"N": 50, "P": 10, "K": 40, "Fe": 0.5}
    result = analyze_nutrient_profile(current, "lettuce", "seedling")
    assert isinstance(result, NutrientAnalysis)
    data = result.as_dict()
    assert "recommended" in data
    assert "deficiencies" in data
    assert "surplus" in data
    assert "balance" in data
    assert "interaction_warnings" in data
    assert "toxicities" in data
    assert data["deficiencies"]
    assert not data["interaction_warnings"]
    assert "ratio_guideline" in data
    assert "npk_ratio" in data
    assert "ratio_delta" in data
