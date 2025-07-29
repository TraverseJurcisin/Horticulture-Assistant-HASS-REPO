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


def test_get_plant_overview():
    overview = ref.get_plant_overview("tomato")
    assert "environment" in overview
    assert "nutrients" in overview
    assert isinstance(overview["environment"], dict)
    assert "water_usage" in overview
    assert overview["water_usage"]["fruiting"] == 320
    assert "total_requirements" in overview
    assert overview["total_requirements"]["N"] == 180
    assert "stage_requirements" in overview
    assert overview["stage_requirements"]["vegetative"]["N"] == 1.8
    assert "ipm" in overview
    assert isinstance(overview["ipm"], dict)
    assert "pest_management" in overview
    assert isinstance(overview["pest_management"], dict)


def test_refresh_reference_data(tmp_path, monkeypatch):
    sample = tmp_path / "dummy.json"
    sample.write_text('{"tomato": {"fruiting": 999}}')

    monkeypatch.delenv("HORTICULTURE_OVERLAY_DIR", raising=False)
    monkeypatch.setitem(ref.REFERENCE_FILES, "dummy_dataset", str(sample))
    ref.refresh_reference_data()
    data1 = ref.load_reference_data()
    assert data1["dummy_dataset"]["tomato"]["fruiting"] == 999

    new_file = tmp_path / "dummy2.json"
    new_file.write_text('{"tomato": {"fruiting": 500}}')
    data2 = ref.load_reference_data()
    # cached value should remain
    assert data2["dummy_dataset"]["tomato"]["fruiting"] == 999

    monkeypatch.setitem(ref.REFERENCE_FILES, "dummy_dataset", str(new_file))
    ref.refresh_reference_data()
    data3 = ref.load_reference_data()
    assert data3["dummy_dataset"]["tomato"]["fruiting"] == 500
