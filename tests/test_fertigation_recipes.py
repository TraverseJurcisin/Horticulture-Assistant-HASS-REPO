from plant_engine.fertigation_recipes import list_supported_plants, get_recipe


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants


def test_get_recipe_case_insensitive():
    recipe = get_recipe("Tomato", "VEGETATIVE")
    assert recipe["urea"] == 0.5


def test_get_recipe_unknown():
    assert get_recipe("unknown", "stage") == {}
