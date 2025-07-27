import json
import pytest
from plant_engine.nutrient_manager import (
    get_recommended_levels,
    get_all_recommended_levels,
    calculate_deficiencies,
    calculate_all_deficiencies,
    calculate_nutrient_balance,
    calculate_surplus,
    calculate_all_surplus,
    calculate_all_nutrient_balance,
    get_npk_ratio,
    get_stage_ratio,
    score_nutrient_levels,
    score_nutrient_series,
    calculate_deficiency_index,
)


def test_get_recommended_levels():
    levels = get_recommended_levels("citrus", "fruiting")
    assert levels["N"] == 120
    assert levels["K"] == 100


def test_calculate_deficiencies():
    current = {"N": 60, "P": 50, "K": 100, "Ca": 50, "Mg": 20}
    defs = calculate_deficiencies(current, "tomato", "fruiting")
    assert defs["N"] == 20
    assert defs["K"] == 20


def test_calculate_nutrient_balance():
    current = {"N": 60, "P": 50, "K": 100}
    ratios = calculate_nutrient_balance(current, "tomato", "fruiting")
    # dataset tomato fruiting: N 80, P 60, K 120
    assert ratios["N"] == 0.75
    assert round(ratios["P"], 2) == round(50 / 60, 2)
    assert round(ratios["K"], 2) == round(100 / 120, 2)


def test_calculate_surplus():
    current = {"N": 150, "P": 70, "K": 130}
    surplus = calculate_surplus(current, "tomato", "fruiting")
    assert surplus["N"] == 70
    assert surplus["P"] == 10
    assert surplus["K"] == 10


def test_get_recommended_levels_case_insensitive():
    levels = get_recommended_levels("Citrus", "FRUITING")
    assert levels["N"] == 120


def test_get_npk_ratio():
    ratio = get_npk_ratio("tomato", "fruiting")
    assert round(ratio["N"] + ratio["P"] + ratio["K"], 2) == 1.0
    assert ratio["N"] == 0.31
    assert ratio["P"] == 0.23
    assert ratio["K"] == 0.46


def test_get_stage_ratio_from_dataset():
    ratio = get_stage_ratio("tomato", "fruiting")
    assert ratio == {"N": 0.27, "P": 0.33, "K": 0.4}


def test_get_stage_ratio_fallback():
    ratio = get_stage_ratio("citrus", "unknown")
    assert ratio == get_npk_ratio("citrus", "unknown")


def test_score_nutrient_levels():
    # Perfect match yields 100
    current = {"N": 80, "P": 60, "K": 120}
    score = score_nutrient_levels(current, "tomato", "fruiting")
    assert score == 100.0

    # 50% deficit on all nutrients yields 50
    deficit = {"N": 40, "P": 30, "K": 60}
    score = score_nutrient_levels(deficit, "tomato", "fruiting")
    assert 49.9 < score < 50.1


def test_score_nutrient_levels_weighted(tmp_path, monkeypatch):
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    weights = {"N": 2.0, "P": 0.5, "K": 0.5}
    (overlay / "nutrient_weights.json").write_text(json.dumps(weights))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))
    import importlib
    import plant_engine.nutrient_manager as nm
    importlib.reload(nm)
    current = {"N": 80, "P": 30, "K": 60}
    score = nm.score_nutrient_levels(current, "tomato", "fruiting")
    assert 80 < score < 90


def test_get_all_recommended_levels():
    levels = get_all_recommended_levels("lettuce", "seedling")
    assert "N" in levels and "Fe" in levels


def test_calculate_all_deficiencies():
    current = {"N": 0.0, "Fe": 0.0}
    defs = calculate_all_deficiencies(current, "lettuce", "seedling")
    assert defs["N"] > 0
    assert defs["Fe"] > 0


def test_calculate_all_surplus():
    current = {"N": 200, "Fe": 5.0}
    surplus = calculate_all_surplus(current, "lettuce", "seedling")
    assert surplus["N"] > 0
    assert surplus["Fe"] > 0


def test_calculate_all_nutrient_balance():
    current = {"N": 100, "Fe": 2.0}
    ratios = calculate_all_nutrient_balance(current, "lettuce", "seedling")
    assert "N" in ratios and "Fe" in ratios
    assert ratios["N"] > 0
    assert ratios["Fe"] > 0


def test_score_nutrient_series():
    s1 = {"N": 80, "P": 60, "K": 120}
    s2 = {"N": 60, "P": 50, "K": 100}
    score = score_nutrient_series([s1, s2], "tomato", "fruiting")
    assert score == (100.0 + score_nutrient_levels(s2, "tomato", "fruiting")) / 2


def test_apply_tag_modifiers():
    from plant_engine import nutrient_manager as nm

    base = {"N": 100, "K": 100}
    adjusted = nm.apply_tag_modifiers(base, ["high-nitrogen", "potassium-sensitive"])
    assert adjusted["N"] == 120.0
    assert adjusted["K"] == 80.0

    unchanged = nm.apply_tag_modifiers(base, ["unknown-tag"])
    assert unchanged == base


def test_get_ph_adjusted_levels():
    from plant_engine.nutrient_manager import get_ph_adjusted_levels

    adjusted = get_ph_adjusted_levels("tomato", "fruiting", 5.0)
    assert adjusted["P"] > 60  # higher target at low pH


def test_get_ph_adjusted_levels_invalid():
    from plant_engine.nutrient_manager import get_ph_adjusted_levels

    with pytest.raises(ValueError):
        get_ph_adjusted_levels("tomato", "fruiting", -1)

    with pytest.raises(ValueError):
        get_ph_adjusted_levels("tomato", "fruiting", 15)


def test_calculate_deficiencies_with_ph():
    from plant_engine.nutrient_manager import calculate_deficiencies_with_ph

    current = {"N": 80, "P": 60, "K": 120}
    deficits = calculate_deficiencies_with_ph(current, "tomato", "fruiting", 5.0)
    assert deficits["P"] > 0


def test_get_all_ph_adjusted_levels():
    from plant_engine.nutrient_manager import get_all_ph_adjusted_levels

    adjusted = get_all_ph_adjusted_levels("tomato", "fruiting", 5.0)
    assert "Fe" in adjusted
    assert adjusted["P"] > 60


def test_calculate_all_deficiencies_with_ph():
    from plant_engine.nutrient_manager import calculate_all_deficiencies_with_ph

    current = {"N": 80, "Fe": 1.0}
    deficits = calculate_all_deficiencies_with_ph(current, "tomato", "fruiting", 5.0)
    assert deficits["P"] > 0
    assert deficits["Fe"] > 0


def test_calculate_deficiency_index():
    guidelines = get_all_recommended_levels("tomato", "fruiting")
    current = {n: 0 for n in guidelines}
    index = calculate_deficiency_index(current, "tomato", "fruiting")
    assert 99 <= index <= 100

    index2 = calculate_deficiency_index(guidelines, "tomato", "fruiting")
    assert index2 == 0.0


def test_calculate_nutrient_adjustments():
    from plant_engine.nutrient_manager import calculate_nutrient_adjustments

    current = {"N": 60, "P": 55, "K": 110}
    adj = calculate_nutrient_adjustments(current, "tomato", "fruiting")
    assert adj["N"] == 20
    assert adj["P"] == 5
    assert adj["K"] == 10


def test_get_stage_adjusted_levels():
    from plant_engine.nutrient_manager import get_stage_adjusted_levels

    levels = get_stage_adjusted_levels("tomato", "fruiting")
    assert levels["N"] == 88.0
    assert levels["K"] == 132.0


def test_get_all_stage_adjusted_levels():
    from plant_engine.nutrient_manager import get_all_stage_adjusted_levels

    levels = get_all_stage_adjusted_levels("tomato", "fruiting")
    assert levels["Ca"] == 66.0
    assert levels["N"] == 88.0


def test_get_synergy_adjusted_levels():
    from plant_engine.nutrient_manager import get_synergy_adjusted_levels

    levels = get_synergy_adjusted_levels("tomato", "fruiting")
    assert levels["P"] == 66.0
    assert round(levels["B"], 2) == 0.53


def test_calculate_all_deficiencies_with_synergy():
    from plant_engine.nutrient_manager import calculate_all_deficiencies_with_synergy

    current = {
        "N": 80,
        "P": 60,
        "K": 120,
        "Ca": 60,
        "Mg": 30,
        "Fe": 4.0,
        "Mn": 1.2,
        "Zn": 0.6,
        "B": 0.5,
        "Cu": 0.1,
        "Mo": 0.05,
    }
    deficits = calculate_all_deficiencies_with_synergy(current, "tomato", "fruiting")
    assert deficits["P"] == 6.0
    assert round(deficits["B"], 2) == 0.03


def test_get_interaction_adjusted_levels():
    from plant_engine.nutrient_manager import get_interaction_adjusted_levels

    levels = get_interaction_adjusted_levels("tomato", "fruiting")
    assert levels["P"] == 66.0
    assert levels["Ca"] == 54.0
    assert round(levels["Zn"], 2) == 0.51


def test_calculate_all_deficiencies_with_interactions():
    from plant_engine.nutrient_manager import calculate_all_deficiencies_with_interactions

    current = {
        "N": 80,
        "P": 60,
        "K": 120,
        "Ca": 60,
        "Mg": 30,
        "Fe": 4.0,
        "Mn": 1.2,
        "Zn": 0.4,
        "B": 0.5,
        "Cu": 0.1,
        "Mo": 0.05,
    }
    deficits = calculate_all_deficiencies_with_interactions(current, "tomato", "fruiting")
    assert deficits["P"] == 6.0
    assert round(deficits["Zn"], 2) == 0.11
