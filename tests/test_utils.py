import os
import pytest

from plant_engine.utils import load_json, normalize_key


def test_normalize_key_lowercase():
    assert normalize_key("Hello") == "hello"


def test_normalize_key_spaces_replaced():
    assert normalize_key("My Plant") == "my_plant"


def test_normalize_key_non_string():
    assert normalize_key(123) == "123"


def test_load_json_success(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"a":1}')
    assert load_json(str(path)) == {"a": 1}


def test_load_json_missing(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        load_json(str(missing))


def test_load_json_invalid(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{oops}")
    with pytest.raises(ValueError):
        load_json(str(bad))
