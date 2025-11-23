from ..engine.plant_engine.nutrient_interactions import (
    analyze_interactions,
    check_imbalances,
    get_balance_action,
    get_interaction_info,
    get_interaction_message,
    get_max_ratio,
    list_interactions,
    recommend_balance_actions,
)


def test_list_interactions():
    pairs = list_interactions()
    assert "K_Mg" in pairs


def test_get_interaction_info():
    info = get_interaction_info("K_Mg")
    assert info["max_ratio"] == 3


def test_get_max_ratio():
    assert get_max_ratio("K", "Mg") == 3
    assert get_max_ratio("Mg", "K") == 3
    assert get_max_ratio("N", "P") == 8
    assert get_max_ratio("X", "Y") is None


def test_get_interaction_message():
    assert "magnesium" in get_interaction_message("K", "Mg")
    assert get_interaction_message("X", "Y") == ""


def test_check_imbalances():
    levels = {"K": 150, "Mg": 20, "Ca": 50, "N": 90, "P": 10}
    warnings = check_imbalances(levels)
    assert "K/Mg" in warnings
    assert "N/P" in warnings


def test_get_balance_action():
    action = get_balance_action("K_Mg")
    assert "magnesium" in action


def test_recommend_balance_actions():
    levels = {"K": 150, "Mg": 20, "Ca": 50, "N": 90, "P": 10}
    actions = recommend_balance_actions(levels)
    assert "K/Mg" in actions
    assert "N/P" in actions


def test_analyze_interactions():
    levels = {"K": 150, "Mg": 20, "N": 90, "P": 10}
    result = analyze_interactions(levels)
    assert "K/Mg" in result
    assert result["K/Mg"]["ratio"] > result["K/Mg"]["max_ratio"]
