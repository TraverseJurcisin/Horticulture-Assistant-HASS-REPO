from plant_engine import (
    environment_manager,
    nutrient_manager,
    growth_stage,
    pest_manager,
    disease_manager,
    fertigation,
)


def test_list_supported_plants():
    plants = environment_manager.list_supported_plants()
    assert "lettuce" in plants
    assert "citrus" in plants
    assert "strawberry" in plants
    assert "basil" in plants
    assert "spinach" in plants
    assert "cucumber" in plants
    assert "pepper" in plants
    assert "arugula" in plants
    assert "blueberry" in plants

    pest_plants = pest_manager.list_supported_plants()
    assert "lettuce" in pest_plants
    assert "cucumber" in pest_plants
    assert "pepper" in pest_plants
    assert "arugula" in pest_plants
    assert "blueberry" in pest_plants

    disease_plants = disease_manager.list_supported_plants()
    assert "lettuce" in disease_plants
    assert "strawberry" in disease_plants
    assert "basil" in disease_plants
    assert "spinach" in disease_plants
    assert "cucumber" in disease_plants
    assert "pepper" in disease_plants
    assert "arugula" in disease_plants
    assert "blueberry" in disease_plants

    purity = fertigation.get_fertilizer_purity("map")
    assert purity["P"] == 0.22

    env_targets = environment_manager.get_environmental_targets("lettuce")
    assert "light_ppfd" in env_targets
    assert "co2_ppm" in env_targets

    berry_env = environment_manager.get_environmental_targets("strawberry")
    assert berry_env["temp_c"] == [18, 26]

    basil_env = environment_manager.get_environmental_targets("basil")
    assert basil_env["humidity_pct"] == [50, 70]

    spinach_env = environment_manager.get_environmental_targets("spinach")
    assert spinach_env["light_ppfd"] == [150, 300]

    cuc_env = environment_manager.get_environmental_targets("cucumber")
    assert cuc_env["temp_c"] == [20, 28]

    pep_env = environment_manager.get_environmental_targets("pepper")
    assert pep_env["humidity_pct"] == [60, 80]

    aru_env = environment_manager.get_environmental_targets("arugula")
    assert aru_env["temp_c"] == [15, 22]

    blue_env = environment_manager.get_environmental_targets("blueberry")
    assert blue_env["humidity_pct"] == [60, 80]


def test_lettuce_stage_info():
    stages = growth_stage.list_growth_stages("lettuce")
    assert "harvest" in stages
    info = growth_stage.get_stage_info("lettuce", "harvest")
    assert info["duration_days"] == 30

    berry_info = growth_stage.get_stage_info("strawberry", "fruiting")
    assert berry_info["duration_days"] == 30

    basil_info = growth_stage.get_stage_info("basil", "harvest")
    assert basil_info["duration_days"] == 20

    spin_info = growth_stage.get_stage_info("spinach", "harvest")
    assert spin_info["duration_days"] == 20

    aru_info = growth_stage.get_stage_info("arugula", "vegetative")
    assert aru_info["duration_days"] == 25

    blue_info = growth_stage.get_stage_info("blueberry", "fruiting")
    assert blue_info["duration_days"] == 40


def test_nutrient_guidelines_lettuce():
    levels = nutrient_manager.get_recommended_levels("lettuce", "seedling")
    assert levels["K"] == 80

    berry_levels = nutrient_manager.get_recommended_levels("strawberry", "fruiting")
    assert berry_levels["K"] == 120

    basil_levels = nutrient_manager.get_recommended_levels("basil", "harvest")
    assert basil_levels["N"] == 60

    spin_levels = nutrient_manager.get_recommended_levels("spinach", "harvest")
    assert spin_levels["P"] == 25

    cuc_levels = nutrient_manager.get_recommended_levels("cucumber", "vegetative")
    assert cuc_levels["K"] == 110

    pep_levels = nutrient_manager.get_recommended_levels("pepper", "fruiting")
    assert pep_levels["N"] == 70

    aru_levels = nutrient_manager.get_recommended_levels("arugula", "vegetative")
    assert aru_levels["K"] == 120

    blue_levels = nutrient_manager.get_recommended_levels("blueberry", "vegetative")
    assert blue_levels["N"] == 60


def test_treatment_guidelines_lettuce():
    pests = pest_manager.recommend_treatments("lettuce", ["aphids"])
    assert pests["aphids"].startswith("Apply")

    diseases = disease_manager.recommend_treatments("lettuce", ["lettuce drop"])
    assert "remove infected" in diseases["lettuce drop"].lower()

    berry_pests = pest_manager.recommend_treatments("strawberry", ["slugs"])
    assert berry_pests["slugs"].startswith("Use bait")

    basil_pests = pest_manager.recommend_treatments("basil", ["aphids"])
    assert basil_pests["aphids"].startswith("Use insecticidal")

    spin_pests = pest_manager.recommend_treatments("spinach", ["leaf miners"])
    assert spin_pests["leaf miners"].startswith("Use row covers")

    berry_dis = disease_manager.recommend_treatments("strawberry", ["botrytis"])
    assert "airflow" in berry_dis["botrytis"].lower()

    basil_dis = disease_manager.recommend_treatments("basil", ["downy mildew"])
    assert "airflow" in basil_dis["downy mildew"].lower()

    spin_dis = disease_manager.recommend_treatments("spinach", ["leaf spot"])
    assert "spacing" in spin_dis["leaf spot"].lower()

    cuc_pests = pest_manager.recommend_treatments("cucumber", ["cucumber beetle"])
    assert cuc_pests["cucumber beetle"].startswith("Apply pyrethrin")

    pep_pests = pest_manager.recommend_treatments("pepper", ["spider mites"])
    assert "neem" in pep_pests["spider mites"].lower()

    aru_pests = pest_manager.recommend_treatments("arugula", ["flea beetles"])
    assert aru_pests["flea beetles"].startswith("Use row covers")

    blue_pests = pest_manager.recommend_treatments("blueberry", ["fruitworms"])
    assert "bacillus" in blue_pests["fruitworms"].lower()

    cuc_dis = disease_manager.recommend_treatments("cucumber", ["bacterial wilt"])
    assert "beetles" in cuc_dis["bacterial wilt"].lower()

    pep_dis = disease_manager.recommend_treatments("pepper", ["bacterial spot"])
    assert "air circulation" in pep_dis["bacterial spot"].lower()

    aru_dis = disease_manager.recommend_treatments("arugula", ["leaf spot"])
    assert "excess moisture" in aru_dis["leaf spot"].lower()

    blue_dis = disease_manager.recommend_treatments("blueberry", ["mummy berry"])
    assert "mummified" in blue_dis["mummy berry"].lower()

    prev = disease_manager.recommend_prevention("lettuce", ["lettuce drop"])
    assert prev["lettuce drop"].startswith("Use clean transplants")
