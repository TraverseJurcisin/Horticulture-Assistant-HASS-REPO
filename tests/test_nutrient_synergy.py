from plant_engine.nutrient_synergy import (
    list_synergy_pairs,
    get_synergy_factor,
    apply_synergy_adjustments,
)


def test_list_synergy_pairs():
    pairs = list_synergy_pairs()
    assert "n_p" in pairs
    assert "ca_b" in pairs


def test_get_synergy_factor_case_insensitive():
    factor = get_synergy_factor("N", "p")
    assert factor == 1.1


def test_apply_synergy_adjustments():
    levels = {"n": 100, "p": 50, "ca": 60, "b": 2}
    adjusted = apply_synergy_adjustments(levels)
    # N/P pair should increase P by 10%
    assert adjusted["p"] == 55.0
    # Ca/B pair increases B by 5%
    assert adjusted["b"] == 2 * 1.05

