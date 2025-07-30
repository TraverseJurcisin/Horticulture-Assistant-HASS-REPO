from plant_engine.datasets import dataset_exists


def test_dataset_exists_true():
    assert dataset_exists("nutrients/nutrient_guidelines.json")


def test_dataset_exists_false():
    assert not dataset_exists("does_not_exist.json")
