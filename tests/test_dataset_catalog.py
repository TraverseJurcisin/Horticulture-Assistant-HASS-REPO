from plant_engine.datasets import list_datasets, get_dataset_description


def test_list_datasets_contains_known():
    datasets = list_datasets()
    assert "nutrient_guidelines.json" in datasets
    assert "irrigation_intervals.json" in datasets
    assert "dataset_catalog.json" not in datasets


def test_list_datasets_includes_subdirectory():
    datasets = list_datasets()
    assert "fertilizers/fertilizer_products.json" in datasets


def test_get_dataset_description():
    desc = get_dataset_description("nutrient_guidelines.json")
    assert "macronutrient" in desc

    desc2 = get_dataset_description("micronutrient_guidelines.json")
    assert "micronutrient" in desc2

    desc3 = get_dataset_description("fertilizer_purity.json")
    assert "purity" in desc3

    desc4 = get_dataset_description("irrigation_intervals.json")
    assert "irrigation" in desc4

    desc5 = get_dataset_description("wsda_fertilizer_database.json")
    assert "WSDA" in desc5
