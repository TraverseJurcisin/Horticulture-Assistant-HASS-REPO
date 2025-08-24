import asyncio

from plant_engine.utils import async_load_dataset, clear_dataset_cache


def test_async_load_dataset(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "sample.json").write_text('{"a": 1}')
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    clear_dataset_cache()

    result = asyncio.run(async_load_dataset("sample.json"))
    assert result == {"a": 1}
