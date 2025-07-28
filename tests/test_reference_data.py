import plant_engine.reference_data as ref


def test_load_reference_data_keys():
    data = ref.load_reference_data()
    for key in ref.REFERENCE_FILES:
        assert key in data
        assert isinstance(data[key], dict)


def test_get_reference_dataset():
    data = ref.get_reference_dataset("ph_guidelines")
    assert isinstance(data, dict)
    assert "citrus" in data
