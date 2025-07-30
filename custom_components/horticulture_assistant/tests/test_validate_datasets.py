from plant_engine import datasets


def test_validate_all_datasets():
    bad = datasets.validate_all_datasets()
    assert bad == []

