from plant_engine.deficiency_manager import (
    list_known_nutrients,
    get_deficiency_symptom,
    diagnose_deficiencies,
    diagnose_deficiencies_detailed,
    get_deficiency_treatment,
    get_nutrient_mobility,
    assess_deficiency_severity,
    recommend_deficiency_treatments,
    diagnose_deficiency_actions,
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
    assert get_nutrient_mobility("Ca") == "immobile"
    assert get_nutrient_mobility("N") == "mobile"


def test_diagnose_deficiencies_detailed():
    guidelines = get_recommended_levels("spinach", "harvest")
    current = {key: 0 for key in guidelines}
    details = diagnose_deficiencies_detailed(current, "spinach", "harvest")
    assert details["N"]["mobility"] == "mobile"
    assert "symptom" in details["N"]


def test_assess_deficiency_severity():
    guidelines = get_recommended_levels("lettuce", "seedling")
    current = {n: 0 for n in guidelines}
    severity = assess_deficiency_severity(current, "lettuce", "seedling")
    assert severity.get("N") == "severe"
    assert severity.get("P") == "severe"


def test_diagnose_deficiency_actions():
    guidelines = get_recommended_levels("lettuce", "seedling")
    current = {n: 0 for n in guidelines}
    actions = diagnose_deficiency_actions(current, "lettuce", "seedling")
    assert actions["N"]["severity"] == "severe"
    assert "nitrogen" in actions["N"]["treatment"].lower()

