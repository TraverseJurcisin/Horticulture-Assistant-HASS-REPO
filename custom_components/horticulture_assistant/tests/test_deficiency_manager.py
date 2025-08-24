import pytest
from plant_engine import deficiency_manager as dm
from plant_engine import utils
from plant_engine.deficiency_manager import (
    assess_deficiency_severity,
    calculate_deficiency_index,
    diagnose_deficiencies,
    diagnose_deficiencies_detailed,
    diagnose_deficiency_actions,
    get_deficiency_symptom,
    get_deficiency_treatment,
    get_nutrient_mobility,
    list_known_nutrients,
    recommend_deficiency_treatments,
    summarize_deficiencies,
    summarize_deficiencies_with_ph,
    summarize_deficiencies_with_ph_and_synergy,
    summarize_deficiencies_with_synergy,
)
from plant_engine.nutrient_manager import get_recommended_levels


@pytest.fixture(autouse=True)
def _reset_cache():
    utils.clear_dataset_cache()
    from plant_engine import deficiency_manager as dm

    dm._symptoms.cache_clear()
    dm._treatments.cache_clear()
    dm._mobility.cache_clear()
    dm._thresholds.cache_clear()
    dm._scores.cache_clear()


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


def test_new_nutrient_entries():
    """Ensure newly added nutrients are recognized."""
    assert "Zn" in list_known_nutrients()
    assert get_nutrient_mobility("Zn") == "immobile"
    assert "boron" in get_deficiency_treatment("B").lower()


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


def test_calculate_deficiency_index():
    guidelines = get_recommended_levels("lettuce", "seedling")
    current = {n: 0 for n in guidelines}
    severity = assess_deficiency_severity(current, "lettuce", "seedling")
    index = calculate_deficiency_index(severity)
    expected = dm._scores().get("severe", 3)
    assert index >= float(expected) - 0.5


def test_summarize_deficiencies():
    guidelines = get_recommended_levels("lettuce", "seedling")
    current = {n: 0 for n in guidelines}
    summary = summarize_deficiencies(current, "lettuce", "seedling")
    expected = dm._scores().get("severe", 3)
    assert summary["severity_index"] >= float(expected) - 0.5
    assert "N" in summary["treatments"]


def test_summarize_deficiencies_with_synergy():
    guidelines = get_recommended_levels("tomato", "fruiting")
    current = {n: 0 for n in guidelines}
    summary = summarize_deficiencies_with_synergy(current, "tomato", "fruiting")
    assert summary["severity_index"] > 0
    assert summary["severity"].get("P") == "severe"


def test_summarize_deficiencies_with_ph():
    guidelines = get_recommended_levels("tomato", "fruiting")
    current = {n: 0 for n in guidelines}
    summary = summarize_deficiencies_with_ph(current, "tomato", "fruiting", 6.5)
    assert summary["severity_index"] > 0
    assert "N" in summary["severity"]


def test_summarize_deficiencies_with_ph_and_synergy():
    guidelines = get_recommended_levels("tomato", "fruiting")
    current = {n: 0 for n in guidelines}
    summary = summarize_deficiencies_with_ph_and_synergy(current, "tomato", "fruiting", 6.5)
    assert summary["severity_index"] > 0
    assert "K" in summary["severity"]
