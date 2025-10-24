import asyncio
import datetime
import itertools
import sys
import types
from pathlib import Path

import pytest

# Minimal Home Assistant stand-ins so tests run without the real package.
ha_pkg = types.ModuleType("homeassistant")
ha_pkg.__path__ = []
sys.modules["homeassistant"] = ha_pkg

core = types.ModuleType("homeassistant.core")


class HomeAssistant:  # pragma: no cover - simple stub
    def __init__(self) -> None:
        self.config = types.SimpleNamespace(components=set(), path=lambda *p: str(Path("/tmp").joinpath(*p)))
        self.data: dict[str, object] = {"integrations": {}}
        self.auth = types.SimpleNamespace(_store=types.SimpleNamespace())
        self.states = _States()
        self.config_entries = _ConfigEntries(self)
        self.services = _ServiceRegistry()
        self.bus = _Bus()

    def async_create_task(self, coro, *_args, **_kwargs):  # pragma: no cover - stub
        return asyncio.create_task(coro)

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    async def async_block_till_done(self):  # pragma: no cover - simple yield
        await asyncio.sleep(0)


class _State:
    def __init__(self, state, attributes=None) -> None:
        self.state = state
        self.attributes = attributes or {}


class _States(dict):
    def async_set(self, entity_id, state, attributes=None) -> None:
        self[entity_id] = _State(state, attributes)


class _ConfigEntries:
    def __init__(self, hass):
        self._entries: dict[str, object] = {}
        self._hass = hass

    async def async_setup(self, entry_id: str) -> None:
        entry = self._entries[entry_id]
        from custom_components.horticulture_assistant import async_setup_entry

        await async_setup_entry(self._hass, entry)

    async def async_forward_entry_setups(self, _entry, _platforms):  # pragma: no cover - stub
        return None


class _ServiceRegistry(dict):
    def async_register(self, domain, service, func, schema=None):  # pragma: no cover - stub
        self[(domain, service)] = func

    async def async_call(self, domain, service, data, blocking=False):  # pragma: no cover - stub
        func = self[(domain, service)]
        result = func(types.SimpleNamespace(data=data))
        if asyncio.iscoroutine(result):
            await result


class _Bus:  # pragma: no cover - minimal event bus
    def async_listen_once(self, *_args, **_kwargs):
        return None


core.HomeAssistant = HomeAssistant
sys.modules["homeassistant.core"] = core

helpers = types.ModuleType("homeassistant.helpers")
helpers.__path__ = []
sys.modules["homeassistant.helpers"] = helpers

# Provide a minimal stand-in for pytest-homeassistant-custom-component so the
# tests can construct mock config entries without the third-party dependency.
if "pytest_homeassistant_custom_component.common" not in sys.modules:
    phcc_pkg = types.ModuleType("pytest_homeassistant_custom_component")
    phcc_common = types.ModuleType("pytest_homeassistant_custom_component.common")

    _ENTRY_COUNTER = itertools.count(1)

    class MockConfigEntry:  # pragma: no cover - trivial helper
        def __init__(
            self,
            *,
            domain: str,
            data: dict | None = None,
            options: dict | None = None,
            title: str | None = None,
            entry_id: str | None = None,
            unique_id: str | None = None,
            version: int = 1,
        ) -> None:
            self.domain = domain
            self.data = dict(data or {})
            self.options = dict(options or {})
            self.title = title
            self.entry_id = entry_id or f"mock-entry-{next(_ENTRY_COUNTER)}"
            self.unique_id = unique_id
            self.version = version
            self.pref_disable_new_entities = False
            self.pref_disable_polling = False
            self._listeners: list[types.FunctionType | types.MethodType] = []

        def add_to_hass(self, hass: HomeAssistant) -> None:
            hass.config_entries._entries[self.entry_id] = self

        def add_update_listener(self, listener):  # pragma: no cover - simple callback
            self._listeners.append(listener)
            return lambda: self._listeners.remove(listener)

        def as_dict(self) -> dict:
            return {
                "entry_id": self.entry_id,
                "domain": self.domain,
                "data": self.data,
                "options": self.options,
                "title": self.title,
                "unique_id": self.unique_id,
                "version": self.version,
            }

    phcc_common.MockConfigEntry = MockConfigEntry
    phcc_pkg.common = phcc_common
    sys.modules["pytest_homeassistant_custom_component"] = phcc_pkg
    sys.modules["pytest_homeassistant_custom_component.common"] = phcc_common

config_validation = types.ModuleType("homeassistant.helpers.config_validation")


def string(value):  # pragma: no cover - minimal validator
    return str(value)


config_validation.string = string
config_validation.config_entry_only_config_schema = lambda schema: schema
sys.modules["homeassistant.helpers.config_validation"] = config_validation

selector = types.ModuleType("homeassistant.helpers.selector")


class SelectSelectorConfig:  # pragma: no cover - minimal container
    def __init__(self, *, options=None, domain=None, device_class=None):
        self.options = options or []
        self.domain = domain
        self.device_class = device_class


class SelectSelector:  # pragma: no cover - minimal container
    def __init__(self, config):
        self.config = config


class EntitySelectorConfig(SelectSelectorConfig):
    pass


class EntitySelector:  # pragma: no cover - minimal container
    def __init__(self, config):
        self.config = config


selector.SelectSelectorConfig = SelectSelectorConfig
selector.SelectSelector = SelectSelector
selector.EntitySelectorConfig = EntitySelectorConfig
selector.EntitySelector = EntitySelector
sys.modules["homeassistant.helpers.selector"] = selector

aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")


def async_get_clientsession(hass):  # pragma: no cover - stubbed
    raise NotImplementedError


aiohttp_client.async_get_clientsession = async_get_clientsession
sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

util = types.ModuleType("homeassistant.util")


def slugify(value: str) -> str:  # pragma: no cover - simple stub
    return value


util.slugify = slugify
util.dt = types.SimpleNamespace(
    utcnow=lambda: datetime.datetime.now(datetime.UTC),
    as_local=lambda value: value,
)
unit_conversion = types.ModuleType("homeassistant.util.unit_conversion")


class TemperatureConverter:  # pragma: no cover - stub returning original value
    @staticmethod
    def convert(value, *_args, **_kwargs):
        return value


unit_conversion.TemperatureConverter = TemperatureConverter
sys.modules["homeassistant.util.unit_conversion"] = unit_conversion
util.unit_conversion = unit_conversion
sys.modules["homeassistant.util"] = util
ha_pkg.util = util

components_pkg = sys.modules.setdefault("homeassistant.components", types.ModuleType("homeassistant.components"))
if "homeassistant.components.sensor" not in sys.modules:
    sensor_module = types.ModuleType("homeassistant.components.sensor")

    class _SensorClass:
        def __init__(self, value: str) -> None:
            self.value = value

    class SensorEntity:  # pragma: no cover - simple base class
        pass

    class SensorStateClass:  # pragma: no cover - simple enum stand-in
        MEASUREMENT = "measurement"

    class SensorDeviceClass:
        TEMPERATURE = _SensorClass("temperature")
        HUMIDITY = _SensorClass("humidity")
        ILLUMINANCE = _SensorClass("illuminance")
        MOISTURE = _SensorClass("moisture")
        CO2 = _SensorClass("co2")
        PH = _SensorClass("ph")
        CONDUCTIVITY = _SensorClass("conductivity")

    sensor_module.SensorDeviceClass = SensorDeviceClass
    sensor_module.SensorEntity = SensorEntity
    sensor_module.SensorStateClass = SensorStateClass
    sys.modules["homeassistant.components.sensor"] = sensor_module
    components_pkg.sensor = sensor_module

# Provide logging helpers used by the pytest HA plugin.
util_logging = types.ModuleType("homeassistant.util.logging")


def log_exception(*_args, **_kwargs):  # pragma: no cover - stub
    return None


util_logging.log_exception = log_exception
sys.modules["homeassistant.util.logging"] = util_logging
util.logging = util_logging

const = types.ModuleType("homeassistant.const")
const.Platform = types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor", SWITCH="switch", NUMBER="number")
const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="°C", FAHRENHEIT="°F")
sys.modules["homeassistant.const"] = const

exceptions = types.ModuleType("homeassistant.exceptions")
exceptions.HomeAssistantError = type("HomeAssistantError", (Exception,), {})
sys.modules["homeassistant.exceptions"] = exceptions

config_entries = types.ModuleType("homeassistant.config_entries")


class ConfigEntry:  # pragma: no cover - minimal stub
    def __init__(self, entry_id: str = "", data=None, options=None, title: str = "") -> None:
        self.entry_id = entry_id
        self.data = data or {}
        self.options = options or {}
        self.title = title


class _BaseFlow:  # pragma: no cover - provide basic flow helpers
    def async_show_form(self, *, step_id, data_schema=None, errors=None):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(self, *, title="", data=None):
        return {"type": "create_entry", "title": title, "data": data or {}}

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}


class ConfigFlow(_BaseFlow):  # pragma: no cover - minimal stub
    def __init_subclass__(cls, *, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.domain = domain


class OptionsFlow(_BaseFlow):  # pragma: no cover - minimal stub
    def __init_subclass__(cls, **kwargs):  # ignore extra kwargs
        super().__init_subclass__(**kwargs)


config_entries.ConfigEntry = ConfigEntry
config_entries.ConfigFlow = ConfigFlow
config_entries.OptionsFlow = OptionsFlow
sys.modules["homeassistant.config_entries"] = config_entries

entity = types.ModuleType("homeassistant.helpers.entity")


class EntityCategory:  # pragma: no cover - minimal stub
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


entity.EntityCategory = EntityCategory
sys.modules["homeassistant.helpers.entity"] = entity

update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")


class DataUpdateCoordinator:
    @classmethod
    def __class_getitem__(cls, _item):  # pragma: no cover - enable typing subscripts
        return cls

    def __init__(self, hass, *_args, **_kwargs):
        self.hass = hass
        self.update_interval = None
        self.last_update_success = True

    async def async_config_entry_first_refresh(self):
        return None


class UpdateFailed(Exception):
    pass


update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
update_coordinator.UpdateFailed = UpdateFailed
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator

storage = types.ModuleType("homeassistant.helpers.storage")

_STORAGE_STATE: dict[str, object] = {}


class Store:  # pragma: no cover - minimal in-memory store
    def __init__(self, _hass, _version, key) -> None:
        self._key = key

    async def async_load(self):
        return _STORAGE_STATE.get(self._key)

    async def async_save(self, data) -> None:
        _STORAGE_STATE[self._key] = data


storage.Store = Store
sys.modules["homeassistant.helpers.storage"] = storage

diagnostics = types.ModuleType("homeassistant.components.diagnostics")

REDACTED = "***REDACTED***"


def async_redact_data(data, keys):
    return {k: (REDACTED if k in keys else v) for k, v in data.items()}


diagnostics.REDACTED = REDACTED
diagnostics.async_redact_data = async_redact_data
sys.modules["homeassistant.components.diagnostics"] = diagnostics


@pytest.fixture
def hass() -> HomeAssistant:
    """Provide a minimal Home Assistant instance."""
    return HomeAssistant()


@pytest.fixture
def enable_custom_integrations():
    """Stub fixture for compatibility with Home Assistant tests."""
    yield
