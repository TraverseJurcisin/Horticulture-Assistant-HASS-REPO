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


def test_dataset_overlay(tmp_path, monkeypatch):
    base = tmp_path / "base"
    overlay = tmp_path / "overlay"
    base.mkdir()
    overlay.mkdir()
    (base / "sample.json").write_text(json.dumps({"foo": 1, "bar": 2}))
    (overlay / "sample.json").write_text(json.dumps({"bar": 5, "baz": 7}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))
    importlib.reload(utils)

    result = utils.load_dataset("sample.json")
    assert result == {"foo": 1, "bar": 5, "baz": 7}


def test_dataset_overlay_deep(tmp_path, monkeypatch):
    base = tmp_path / "base"
    overlay = tmp_path / "overlay"
    base.mkdir()
    overlay.mkdir()
    (base / "sample.json").write_text(json.dumps({"foo": {"a": 1, "b": 2}, "bar": 2}))
    (overlay / "sample.json").write_text(json.dumps({"foo": {"b": 5, "c": 9}}))

    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    monkeypatch.setenv("HORTICULTURE_OVERLAY_DIR", str(overlay))
    importlib.reload(utils)

    result = utils.load_dataset("sample.json")
    assert result == {"foo": {"a": 1, "b": 5, "c": 9}, "bar": 2}
