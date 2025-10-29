import pytest

from plant_engine.nutrient_manager import calculate_cycle_deficiency_index


def test_calculate_cycle_deficiency_index():
    levels = {
        "vegetative": {
            "N": 50,
            "P": 40,
            "K": 60,
            "Ca": 30,
            "Mg": 20,
            "Fe": 0.5,
            "Mn": 0.2,
            "Zn": 0.1,
        },
        "fruiting": {
            "N": 60,
            "P": 50,
            "K": 100,
            "Ca": 40,
            "Mg": 25,
            "Fe": 0.5,
            "Mn": 0.2,
            "Zn": 0.1,
        },
    }
    result = calculate_cycle_deficiency_index(levels, "tomato")
    assert set(result.keys()) == {"vegetative", "fruiting"}
    assert pytest.approx(result["vegetative"], rel=1e-2) == 49.0
    assert pytest.approx(result["fruiting"], rel=1e-2) == 45.1
