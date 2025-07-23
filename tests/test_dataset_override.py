import importlib
import json

import plant_engine.utils as utils


def test_dataset_env_override(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    test_data = {"foo": 1}
    (data_dir / "sample.json").write_text(json.dumps(test_data))
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(data_dir))
    importlib.reload(utils)
    result = utils.load_dataset("sample.json")
    assert result == test_data
