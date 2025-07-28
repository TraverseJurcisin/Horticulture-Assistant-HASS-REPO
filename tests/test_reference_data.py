import plant_engine.reference_data as ref


def test_load_reference_data_keys():
    data = ref.load_reference_data()
    for key in ref.REFERENCE_FILES:
        assert key in data
        assert isinstance(data[key], dict)


def test_get_reference_dataset():
    synergy = ref.get_reference_dataset("nutrient_synergies")
    assert isinstance(synergy, dict)
    assert "n_p" in synergy
