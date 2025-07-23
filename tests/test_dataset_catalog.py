from plant_engine.datasets import list_datasets, get_dataset_description


def test_list_datasets_contains_known():
    datasets = list_datasets()
    assert "nutrient_guidelines.json" in datasets
    assert "dataset_catalog.json" not in datasets


def test_get_dataset_description():
    desc = get_dataset_description("nutrient_guidelines.json")
    assert "macronutrient" in desc
    assert "pest" in get_dataset_description("beneficial_insects.json")
