from plant_engine.datasets import list_dataset_info


def test_list_dataset_info_contains_descriptions():
    info = list_dataset_info()
    assert "nutrient_guidelines.json" in info
    assert isinstance(info["nutrient_guidelines.json"], str)
