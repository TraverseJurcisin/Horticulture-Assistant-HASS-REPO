from plant_engine.deficiency_manager import (
    list_known_nutrients,
    get_deficiency_symptom,
    diagnose_deficiencies,
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

