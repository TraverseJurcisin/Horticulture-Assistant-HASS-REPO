from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path

import custom_components  # noqa: F401  # ensure base package is registered

# The integration's ``__init__`` imports ``homeassistant.components.sensor``
# which is not available in tests. Provide a lightweight stand-in so the module
# can be imported without Home Assistant installed.
if "homeassistant.components" not in sys.modules:
    sys.modules["homeassistant.components"] = types.ModuleType("homeassistant.components")

if "homeassistant.components.sensor" not in sys.modules:
    sensor_module = types.ModuleType("homeassistant.components.sensor")

    class _SensorClass:
        def __init__(self, value: str) -> None:
            self.value = value

    class SensorDeviceClass:
        TEMPERATURE = _SensorClass("temperature")
        HUMIDITY = _SensorClass("humidity")
        ILLUMINANCE = _SensorClass("illuminance")
        MOISTURE = _SensorClass("moisture")
        CO2 = _SensorClass("co2")
        PH = _SensorClass("ph")

    sensor_module.SensorDeviceClass = SensorDeviceClass
    sensor_module.SensorEntity = type("SensorEntity", (), {})
    sensor_module.SensorStateClass = type("SensorStateClass", (), {"MEASUREMENT": "measurement"})
    sys.modules["homeassistant.components.sensor"] = sensor_module

core_module = sys.modules.setdefault("homeassistant.core", types.ModuleType("homeassistant.core"))

if not hasattr(core_module, "callback"):

    def callback(func):
        return func

    core_module.callback = callback

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant"

ha_pkg_name = "custom_components.horticulture_assistant"
ha_pkg = sys.modules.get(ha_pkg_name)
if ha_pkg is None:
    ha_pkg = types.ModuleType(ha_pkg_name)
    ha_pkg.__path__ = [str(PACKAGE_ROOT)]
    sys.modules[ha_pkg_name] = ha_pkg

utils_pkg_name = f"{ha_pkg_name}.utils"
utils_pkg = sys.modules.get(utils_pkg_name)
if utils_pkg is None:
    utils_pkg = types.ModuleType(utils_pkg_name)
    utils_pkg.__path__ = [str(PACKAGE_ROOT / "utils")]
    sys.modules[utils_pkg_name] = utils_pkg

spec = importlib.util.spec_from_file_location(
    f"{utils_pkg_name}.profile_helpers",
    PACKAGE_ROOT / "utils" / "profile_helpers.py",
)
profile_helpers = importlib.util.module_from_spec(spec)
profile_helpers.__package__ = utils_pkg_name
sys.modules[spec.name] = profile_helpers
assert spec.loader is not None
spec.loader.exec_module(profile_helpers)

write_profile_sections = profile_helpers.write_profile_sections


def test_write_profile_sections_overwrite_logging(tmp_path, caplog):
    """Ensure overwrite flag logs created vs overwritten correctly."""

    caplog.set_level(logging.INFO)
    sections = {"profile.json": {"foo": "bar"}}

    result = write_profile_sections(
        "plant-1",
        sections,
        base_path=tmp_path,
        overwrite=True,
    )
    assert result == "plant-1"
    assert any(message.startswith("Created file:") for message in caplog.messages), caplog.messages

    caplog.clear()

    result = write_profile_sections(
        "plant-1",
        sections,
        base_path=tmp_path,
        overwrite=True,
    )
    assert result == "plant-1"
    assert any(message.startswith("Overwrote existing file:") for message in caplog.messages), caplog.messages


def test_write_profile_sections_returns_empty_when_all_writes_fail(tmp_path, monkeypatch, caplog):
    """Return an empty string when no files could be written."""

    caplog.set_level(logging.ERROR)

    def raise_io_error(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(profile_helpers, "save_json", raise_io_error)

    result = write_profile_sections(
        "plant-2",
        {"profile.json": {"foo": "bar"}},
        base_path=tmp_path,
    )

    assert result == ""
    assert any("Unable to create any profile files" in message for message in caplog.messages)
