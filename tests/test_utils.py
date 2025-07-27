import pytest

import importlib

import plant_engine.utils as utils
from plant_engine.utils import (
    load_json,
    normalize_key,
    clear_dataset_cache,
    stage_value,
    load_stage_dataset_value,
)


def test_normalize_key_lowercase():
    assert normalize_key("Hello") == "hello"


def test_normalize_key_spaces_replaced():
    assert normalize_key("My Plant") == "my_plant"


def test_normalize_key_non_string():
    assert normalize_key(123) == "123"


def test_load_json_success(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"a":1}')
    assert load_json(path) == {"a": 1}


def test_load_json_missing(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        load_json(missing)


def test_load_json_invalid(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops}")
    with pytest.raises(ValueError):
        load_json(bad)


def test_clear_dataset_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("HORTICULTURE_DATA_DIR", raising=False)
    monkeypatch.delenv("HORTICULTURE_OVERLAY_DIR", raising=False)
    base1 = tmp_path / "d1"
    base1.mkdir()
    (base1 / "sample.json").write_text('{"a":1}')
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base1))
    clear_dataset_cache()
    importlib.reload(utils)
    first = utils.load_dataset("sample.json")
    assert first == {"a": 1}

    base2 = tmp_path / "d2"
    base2.mkdir()
    (base2 / "sample.json").write_text('{"a":2}')
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base2))
    clear_dataset_cache()
    importlib.reload(utils)
    second = utils.load_dataset("sample.json")
    assert second == {"a": 2}


def test_stage_value_fallback():
    data = {"lettuce": {"seedling": "A", "optimal": "B"}}
    assert stage_value(data, "lettuce", "seedling") == "A"
    assert stage_value(data, "lettuce", None) == "B"
    assert stage_value(data, "lettuce", "unknown") == "B"


def test_stage_value_custom_default():
    data = {"crop": {"phase": 1, "default": 2}}
    assert stage_value(data, "crop", "missing", default_key="default") == 2


def test_load_stage_dataset_value():
    value = load_stage_dataset_value(
        "soil_moisture_guidelines.json", "citrus", "seedling"
    )
    assert value == [30, 50]

    # missing stage falls back to the dataset's 'optimal' entry
    assert load_stage_dataset_value(
        "soil_moisture_guidelines.json", "citrus", "missing"
    ) == [30, 50]


def test_load_datasets(monkeypatch, tmp_path):
    base = tmp_path / "data"
    base.mkdir()
    (base / "one.json").write_text('{"a": 1}')
    (base / "two.json").write_text('{"b": 2}')
    monkeypatch.setenv("HORTICULTURE_DATA_DIR", str(base))
    clear_dataset_cache()
    import importlib
    import plant_engine.utils as utils
    importlib.reload(utils)
    data = utils.load_datasets("one.json", "two.json")
    assert data == {"one.json": {"a": 1}, "two.json": {"b": 2}}

