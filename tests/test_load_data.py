import json
import pytest
from plant_engine.utils import load_data


def test_load_yaml(tmp_path):
    path = tmp_path / "sample.yaml"
    path.write_text("a: 1\nb: 2\n")
    assert load_data(str(path)) == {"a": 1, "b": 2}


def test_load_data_invalid_yaml(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("- [unterminated")
    with pytest.raises(ValueError):
        load_data(str(path))


def test_load_data_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_data(str(tmp_path / 'none.yaml'))

