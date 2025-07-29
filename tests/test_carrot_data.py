from plant_engine.environment_manager import get_environmental_targets
from plant_engine.nutrient_manager import get_recommended_levels
from plant_engine.pest_manager import get_pest_guidelines
from plant_engine.growth_stage import get_stage_duration


def test_carrot_environment_targets():
    data = get_environmental_targets("carrot")
    assert data["temp_c"] == [16, 24]


def test_carrot_nutrient_levels():
    levels = get_recommended_levels("carrot", "vegetative")
    assert levels["N"] == 60


def test_carrot_pest_guidelines():
    guide = get_pest_guidelines("carrot")
    assert "carrot rust fly" in guide


def test_carrot_growth_stage():
    assert get_stage_duration("carrot", "vegetative") == 70
