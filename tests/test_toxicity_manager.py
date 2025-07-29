from plant_engine.toxicity_manager import (
    list_supported_plants,
    get_toxicity_thresholds,
    check_toxicities,
    list_known_nutrients,
    get_toxicity_symptom,
    diagnose_toxicities,
    get_toxicity_treatment,
    recommend_toxicity_treatments,
    calculate_toxicity_index,
)
from plant_engine.utils import clear_dataset_cache


def test_list_supported_plants():
    plants = list_supported_plants()
    assert "tomato" in plants
    assert "lettuce" in plants


def test_list_known_nutrients():
    nutrients = list_known_nutrients()
    assert "N" in nutrients


def test_get_toxicity_thresholds():
    thresh = get_toxicity_thresholds("tomato")
    assert thresh["K"] == 350
    default = get_toxicity_thresholds("unknown")
    assert default["N"] == 200


def test_check_toxicities():
    current = {"N": 260, "K": 340, "Fe": 3}
    excess = check_toxicities(current, "tomato")
    assert excess["N"] == 10
    assert "K" not in excess
    assert "Fe" not in excess


def test_toxicity_symptom_and_treatment():
    assert "burn" in get_toxicity_symptom("N").lower()
    assert get_toxicity_treatment("P")


def test_diagnose_and_recommend_treatments():
    current = {"N": 260, "K": 400}
    symptoms = diagnose_toxicities(current, "tomato")
    actions = recommend_toxicity_treatments(current, "tomato")
    assert "N" in symptoms and "burn" in symptoms["N"].lower()
    assert "K" in actions and actions["K"]


def test_calculate_toxicity_index():
    clear_dataset_cache()
    import importlib
    import plant_engine.nutrient_manager as nm
    importlib.reload(nm)
    import plant_engine.toxicity_manager as tm
    importlib.reload(tm)
    levels = {"N": 300, "K": 400}
    index = tm.calculate_toxicity_index(levels, "tomato")
    assert index == 17.1
