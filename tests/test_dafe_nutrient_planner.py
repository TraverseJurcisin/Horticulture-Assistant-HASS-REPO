from dafe.nutrient_planner import get_stage_targets, calculate_daily_nutrient_mass


def test_get_stage_targets():
    levels = get_stage_targets("tomato", "vegetative")
    assert levels["N"] == 100
    assert "K" in levels


def test_calculate_daily_nutrient_mass():
    mass = calculate_daily_nutrient_mass("tomato", "vegetative", 2000)
    assert mass["N"] == 200.0
    assert mass["P"] == 100.0
