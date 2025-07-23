import importlib
import json
import os

import plant_engine.utils as utils


def test_dataset_extra_dirs(tmp_path, monkeypatch):
    base = tmp_path / "base"
    extra1 = tmp_path / "extra1"
    extra2 = tmp_path / "extra2"
    base.mkdir()
    extra1.mkdir()
    extra2.mkdir()

    (base / "sample.json").write_text(json.dumps({"a": 1}))
    (extra1 / "sample.json").write_text(json.dumps({"b": 2}))
    (extra2 / "sample.json").write_text(json.dumps({"b": 3, "c": 4}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    dirs = os.pathsep.join([str(extra1), str(extra2)])
    monkeypatch.setenv("HORTICULTURE_EXTRA_DATA_DIRS", dirs)

    importlib.reload(utils)

    result = utils.load_dataset("sample.json")
    assert result == {"a": 1, "b": 3, "c": 4}




def test_dataset_extra_dirs_with_overlay(tmp_path, monkeypatch):
    base = tmp_path / "base"
    extra = tmp_path / "extra"
    overlay = tmp_path / "overlay"
    base.mkdir()
    extra.mkdir()
    overlay.mkdir()

    (base / "sample.json").write_text(json.dumps({"val": 1}))
    (extra / "sample.json").write_text(json.dumps({"val": 2}))
    (overlay / "sample.json").write_text(json.dumps({"val": 3}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_EXTRA_DATA_DIRS", str(extra))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))

    importlib.reload(utils)

    result = utils.load_dataset("sample.json")
    assert result == {"val": 3}

