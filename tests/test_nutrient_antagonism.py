from plant_engine.nutrient_antagonism import (
    list_antagonism_pairs,
    get_antagonism_factor,
    apply_antagonism_adjustments,
)


def test_list_antagonism_pairs():
    pairs = list_antagonism_pairs()
    assert "k_ca" in pairs
    assert "p_zn" in pairs


def test_get_antagonism_factor_case_insensitive():
    assert get_antagonism_factor("K", "CA") == 0.9


def test_apply_antagonism_adjustments():
    levels = {"k": 200, "ca": 100, "p": 50, "zn": 10}
    adjusted = apply_antagonism_adjustments(levels)
    assert adjusted["ca"] == 90.0
    assert adjusted["zn"] == 8.5
