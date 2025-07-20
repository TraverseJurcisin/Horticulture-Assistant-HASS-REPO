from plant_engine import (
    environment_manager,
    nutrient_manager,
    growth_stage,
    pest_manager,
    disease_manager,
)


def test_list_supported_plants():
    plants = environment_manager.list_supported_plants()
    assert "lettuce" in plants
    assert "citrus" in plants

    pest_plants = pest_manager.list_supported_plants()
    assert "lettuce" in pest_plants

    disease_plants = disease_manager.list_supported_plants()
    assert "lettuce" in disease_plants


def test_lettuce_stage_info():
    stages = growth_stage.list_growth_stages("lettuce")
    assert "harvest" in stages
    info = growth_stage.get_stage_info("lettuce", "harvest")
    assert info["duration_days"] == 30


def test_nutrient_guidelines_lettuce():
    levels = nutrient_manager.get_recommended_levels("lettuce", "seedling")
    assert levels["K"] == 80


def test_treatment_guidelines_lettuce():
    pests = pest_manager.recommend_treatments("lettuce", ["aphids"])
    assert pests["aphids"].startswith("Apply")

    diseases = disease_manager.recommend_treatments("lettuce", ["lettuce drop"])
    assert "remove infected" in diseases["lettuce drop"].lower()
