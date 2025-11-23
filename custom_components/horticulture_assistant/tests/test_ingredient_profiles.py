from ..engine.plant_engine.ingredients import get_ingredient_profile, list_ingredients


def test_get_ingredient_profile():
    profile = get_ingredient_profile("urea")
    assert profile
    assert profile.nutrient_content["N"] == 0.46
    assert profile.chemical_formula == "CO(NH2)2"


def test_alias_lookup():
    profile = get_ingredient_profile("Epsom Salt")
    assert profile
    assert profile.name == "magnesium_sulfate"
    assert profile.form == "solid"


def test_list_ingredients():
    ingredients = list_ingredients()
    assert "urea" in ingredients
    assert "magnesium_sulfate" in ingredients
