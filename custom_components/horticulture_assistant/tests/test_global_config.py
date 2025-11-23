from pathlib import Path

from ..utils import global_config


class DummyConfig:
    def __init__(self, base):
        self._base = Path(base)

    def path(self, *parts):
        return str(self._base.joinpath(*parts))


class DummyHass:
    def __init__(self, base):
        self.config = DummyConfig(base)
        self.data = {}


def test_load_config_defaults(tmp_path):
    hass = DummyHass(tmp_path)
    cfg = global_config.load_config(hass)
    assert cfg == global_config.DEFAULTS


def test_save_and_merge(tmp_path):
    hass = DummyHass(tmp_path)
    global_config.save_config({"use_openai": True}, hass)
    cfg = global_config.load_config(hass)
    assert cfg["use_openai"] is True
    assert cfg["openai_api_key"] == ""
    assert cfg["openai_model"] == "gpt-4o"
    assert cfg["openai_temperature"] == 0.3
    assert cfg["default_threshold_mode"] == "profile"
