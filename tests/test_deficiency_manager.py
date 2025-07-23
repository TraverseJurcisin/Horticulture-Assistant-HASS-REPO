from plant_engine.deficiency_manager import (
    list_known_nutrients,
    get_deficiency_symptom,
    diagnose_deficiencies,
    get_deficiency_treatment,
    recommend_deficiency_treatments,
    get_nutrient_mobility,
    classify_mobility,
)
from plant_engine.nutrient_manager import get_recommended_levels


def test_list_known_nutrients():
    nutrients = list_known_nutrients()
    assert "N" in nutrients
    assert "Fe" in nutrients


def test_get_deficiency_symptom():
    assert "yellow" in get_deficiency_symptom("N").lower()
    assert get_deficiency_symptom("unknown") == ""


def test_diagnose_deficiencies():
    # choose spinach harvest stage as dataset exists
    guidelines = get_recommended_levels("spinach", "harvest")
    # current levels missing N and Mg
    current = {key: 0 for key in guidelines}
    symptoms = diagnose_deficiencies(current, "spinach", "harvest")
    assert "N" in symptoms
    assert "Mg" in symptoms


def test_get_deficiency_treatment():
    treat = get_deficiency_treatment("N")
    assert "nitrogen" in treat.lower() or "compost" in treat.lower()
    assert get_deficiency_treatment("unknown") == ""


def test_recommend_deficiency_treatments():
    guidelines = get_recommended_levels("spinach", "harvest")
    current = {key: 0 for key in guidelines}
    actions = recommend_deficiency_treatments(current, "spinach", "harvest")
    assert "N" in actions and actions["N"]


def test_get_nutrient_mobility():
    assert get_nutrient_mobility("N") == "mobile"
    assert get_nutrient_mobility("Ca") == "immobile"
    assert get_nutrient_mobility("unknown") == ""


def test_classify_mobility():
    result = classify_mobility(["N", "Fe", "Mo"])
    assert result == {"N": "mobile", "Fe": "immobile", "Mo": "mobile"}

