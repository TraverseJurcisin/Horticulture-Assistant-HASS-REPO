from ..engine.plant_engine.nutrient_manager import get_recommended_levels
from ..engine.plant_engine.surplus_manager import get_surplus_action, list_known_nutrients, recommend_surplus_actions


def test_list_known_nutrients():
    nutrients = list_known_nutrients()
    assert "N" in nutrients


def test_get_surplus_action():
    action = get_surplus_action("N")
    assert "leach" in action.lower()
    assert get_surplus_action("unknown") == ""


def test_recommend_surplus_actions():
    guidelines = get_recommended_levels("tomato", "fruiting")
    # create levels double the recommended to ensure surplus
    current = {k: v * 2 for k, v in guidelines.items()}
    actions = recommend_surplus_actions(current, "tomato", "fruiting")
    assert "N" in actions
