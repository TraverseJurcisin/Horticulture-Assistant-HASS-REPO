from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant"
MODULE_NAME = "custom_components.horticulture_assistant.services"

# Ensure the package placeholder exists without importing the real integration
pkg_name = "custom_components.horticulture_assistant"
if pkg_name not in sys.modules:
    pkg = types.ModuleType(pkg_name)
    pkg.__path__ = [str(PACKAGE_ROOT)]
    sys.modules[pkg_name] = pkg

# Provide lightweight stubs for dependencies that require Home Assistant
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
        CONDUCTIVITY = _SensorClass("conductivity")

    sensor_module.SensorDeviceClass = SensorDeviceClass
    sys.modules["homeassistant.components.sensor"] = sensor_module

if "homeassistant.config_entries" not in sys.modules:
    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:  # pragma: no cover - minimal placeholder
        pass

    config_entries.ConfigEntry = ConfigEntry
    sys.modules["homeassistant.config_entries"] = config_entries

if "homeassistant.exceptions" not in sys.modules:
    exceptions_mod = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    exceptions_mod.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant.exceptions"] = exceptions_mod

# Stub optional integration modules referenced by services
profile_registry_mod = sys.modules.get(f"{pkg_name}.profile_registry")
if profile_registry_mod is None:
    profile_registry_mod = types.ModuleType(f"{pkg_name}.profile_registry")

    class ProfileRegistry:  # pragma: no cover - minimal placeholder
        pass

    profile_registry_mod.ProfileRegistry = ProfileRegistry
    sys.modules[f"{pkg_name}.profile_registry"] = profile_registry_mod

storage_mod = sys.modules.get(f"{pkg_name}.storage")
if storage_mod is None:
    storage_mod = types.ModuleType(f"{pkg_name}.storage")

    class LocalStore:  # pragma: no cover - minimal placeholder
        pass

    storage_mod.LocalStore = LocalStore
    sys.modules[f"{pkg_name}.storage"] = storage_mod

irrigation_mod = sys.modules.get(f"{pkg_name}.irrigation_bridge")
if irrigation_mod is None:
    irrigation_mod = types.ModuleType(f"{pkg_name}.irrigation_bridge")

    async def async_apply_irrigation(*_args, **_kwargs):  # pragma: no cover - placeholder
        return None

    irrigation_mod.async_apply_irrigation = async_apply_irrigation
    sys.modules[f"{pkg_name}.irrigation_bridge"] = irrigation_mod

# Load the services module directly from file to avoid importing __init__
services_path = PACKAGE_ROOT / "services.py"
spec = importlib.util.spec_from_file_location(MODULE_NAME, services_path)
assert spec and spec.loader
services_module = importlib.util.module_from_spec(spec)
sys.modules[MODULE_NAME] = services_module
spec.loader.exec_module(services_module)


def test_measurement_classes_include_extended_roles():
    """CO₂ and pH roles should map to the correct device classes."""

    assert "co2" in services_module.MEASUREMENT_CLASSES
    assert services_module.MEASUREMENT_CLASSES["co2"] is services_module.SensorDeviceClass.CO2
    assert "ph" in services_module.MEASUREMENT_CLASSES
    assert services_module.MEASUREMENT_CLASSES["ph"] is services_module.SensorDeviceClass.PH
    assert "conductivity" in services_module.MEASUREMENT_CLASSES
    assert services_module.MEASUREMENT_CLASSES["conductivity"] is services_module.SensorDeviceClass.CONDUCTIVITY
