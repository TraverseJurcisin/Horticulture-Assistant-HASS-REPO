from ..engine.plant_engine.utils import clear_dataset_cache, list_dataset_files


def test_list_dataset_files(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "foo.json").write_text("{}")
    (data_dir / "bar.yaml").write_text("a: 1")
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    clear_dataset_cache()
    files = list_dataset_files()
    assert set(files) == {"foo.json", "bar.yaml"}
