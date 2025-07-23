from plant_engine.nutrient_interactions import (
    list_interactions,
    get_interaction_info,
    get_max_ratio,
    check_imbalances,
    get_balance_action,
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
