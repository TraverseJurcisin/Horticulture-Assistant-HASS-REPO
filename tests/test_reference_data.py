import pytest
import plant_engine.reference_data as ref


def test_load_reference_data_keys():
    data = ref.load_reference_data()
    for key in ref.REFERENCE_FILES:
        assert key in data
        assert isinstance(data[key], dict)


def test_get_reference_dataset_valid():
    for key in ref.REFERENCE_FILES:
        ds = ref.get_reference_dataset(key)
        assert isinstance(ds, dict)


def test_get_reference_dataset_invalid():
    with pytest.raises(KeyError):
        ref.get_reference_dataset("unknown")
