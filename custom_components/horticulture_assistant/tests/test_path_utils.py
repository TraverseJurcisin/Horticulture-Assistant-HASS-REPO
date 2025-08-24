import os
from pathlib import Path

from custom_components.horticulture_assistant.utils import path_utils


class DummyConfig:
    def __init__(self, base):
        self._base = Path(base)

    def path(self, *parts):
        return str(self._base.joinpath(*parts))


class DummyHass:
    def __init__(self, base):
        self.config = DummyConfig(base)
        self.data = {}


def test_ensure_dir_creates(tmp_path):
    hass = DummyHass(tmp_path)
    path = path_utils.ensure_dir(hass, "foo")
    assert Path(path).is_dir()
    assert path == os.path.join(tmp_path, "foo")


def test_ensure_data_plants_dir(tmp_path):
    hass = DummyHass(tmp_path)
    dpath = path_utils.ensure_data_dir(hass, "sub")
    ppath = path_utils.ensure_plants_dir(hass, "one")
    assert Path(dpath).is_dir()
    assert Path(ppath).is_dir()
    assert dpath.endswith(os.path.join("data", "sub"))
    assert ppath.endswith(os.path.join("plants", "one"))
