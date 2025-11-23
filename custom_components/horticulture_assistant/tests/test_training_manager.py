from ..engine.plant_engine.training_manager import get_training_guideline, list_supported_plants, list_training_stages


def test_list_supported_plants_contains_known():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert "citrus" in plants


def test_list_training_stages():
    stages = list_training_stages("tomato")
    assert "seedling" in stages
    assert "vegetative" in stages


def test_get_training_guideline_case_insensitive():
    guid = get_training_guideline("ToMaTo", "VeGeTaTiVe")
    assert "prune" in guid.lower()


def test_get_training_guideline_unknown():
    assert get_training_guideline("unknown", "stage") is None
