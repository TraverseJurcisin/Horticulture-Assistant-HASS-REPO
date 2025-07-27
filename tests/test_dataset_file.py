import importlib
import json
import os

import plant_engine.utils as utils


def test_dataset_file_resolves_paths(tmp_path, monkeypatch):
    base = tmp_path / "data"
    overlay = tmp_path / "overlay"
    base.mkdir()
    overlay.mkdir()

    (base / "sample.json").write_text(json.dumps({"a": 1}))
    (overlay / "sample.json").write_text(json.dumps({"a": 2}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))

    importlib.reload(utils)

    assert utils.dataset_file("sample.json") == overlay / "sample.json"

    (overlay / "sample.json").unlink()
    utils.clear_dataset_cache()
    importlib.reload(utils)

    assert utils.dataset_file("sample.json") == base / "sample.json"
