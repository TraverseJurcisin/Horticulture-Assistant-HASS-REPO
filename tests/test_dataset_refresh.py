import json
import importlib

import plant_engine.utils as utils
import plant_engine.datasets as datasets


def test_refresh_datasets_reload(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    file = data_dir / "sample.json"
    file.write_text(json.dumps({"a": 1}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    importlib.reload(utils)
    importlib.reload(datasets)

    assert utils.load_dataset("sample.json") == {"a": 1}

    file.write_text(json.dumps({"a": 2}))

    # Cached result should still return original value
    assert utils.load_dataset("sample.json") == {"a": 1}

    datasets.refresh_datasets()

    # After refresh we should get the updated value
    assert utils.load_dataset("sample.json") == {"a": 2}
