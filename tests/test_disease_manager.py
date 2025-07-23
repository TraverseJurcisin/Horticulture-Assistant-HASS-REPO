from plant_engine.disease_manager import (
    get_disease_guidelines,
    recommend_treatments,
    list_known_diseases,
)


def test_get_disease_guidelines():
    guide = get_disease_guidelines("citrus")
    assert "root rot" in guide
    assert guide["citrus greening"].startswith("Remove infected")


def test_get_disease_guidelines_case_insensitive():
    guide = get_disease_guidelines("CiTrUs")
    assert "root rot" in guide


def test_recommend_treatments():
    actions = recommend_treatments("citrus", ["root rot", "unknown"])
    assert actions["root rot"].startswith("Ensure good drainage")
    assert actions["unknown"] == "No guideline available"


def test_list_known_diseases():
    diseases = list_known_diseases("citrus")
    assert "root rot" in diseases
