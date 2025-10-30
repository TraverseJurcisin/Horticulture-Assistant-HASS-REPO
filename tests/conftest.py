import asyncio
import datetime
import sys
import types
from collections.abc import Callable
from copy import deepcopy
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
        self.helpers = types.SimpleNamespace(aiohttp_client=None)

    def async_create_task(self, coro, *_args, **_kwargs):  # pragma: no cover - stub
        return asyncio.create_task(coro)

    async def async_add_executor_job(self, func, *args, **kwargs):
        return func(*args, **kwargs)

    async def async_block_till_done(self):  # pragma: no cover - simple yield
        await asyncio.sleep(0)


class _State:
    def __init__(self, entity_id, state, attributes=None) -> None:
        self.entity_id = entity_id
        self.state = state
        self.attributes = attributes or {}
        self.name = self.attributes.get("friendly_name")
        self.domain = entity_id.split(".")[0] if isinstance(entity_id, str) else ""


class _States(dict):
    def async_set(self, entity_id, state, attributes=None) -> None:
        self[entity_id] = _State(entity_id, state, attributes)

    def entity_ids(self):  # pragma: no cover - helper for catalog suggestions
        return list(self.keys())

    def async_entity_ids(self):  # pragma: no cover - helper for catalog suggestions
        return self.entity_ids()


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

    def async_update_entry(self, entry, *, data=None, options=None):
        if data is not None:
            entry.data = data
        if options is not None:
            entry.options = options
        self._entries[getattr(entry, "entry_id", "")] = entry


class _ServiceRegistry(dict):
    def async_register(self, domain, service, func, schema=None):  # pragma: no cover - stub
        self[(domain, service)] = func

    async def async_call(self, domain, service, data, blocking=False):  # pragma: no cover - stub
        func = self.get((domain, service))
        if func is None:
            return None
        result = func(types.SimpleNamespace(data=data))
        if asyncio.iscoroutine(result):
            await result


class _Bus:  # pragma: no cover - minimal event bus
    def async_listen_once(self, *_args, **_kwargs):
        return None


core.HomeAssistant = HomeAssistant
core.CALLBACK_TYPE = Callable[[], None]
sys.modules["homeassistant.core"] = core

helpers = types.ModuleType("homeassistant.helpers")
helpers.__path__ = []
sys.modules["homeassistant.helpers"] = helpers

config_validation = types.ModuleType("homeassistant.helpers.config_validation")


def string(value):  # pragma: no cover - minimal validator
    return str(value)


config_validation.string = string
config_validation.config_entry_only_config_schema = lambda schema: schema
sys.modules["homeassistant.helpers.config_validation"] = config_validation

selector = types.ModuleType("homeassistant.helpers.selector")


class _BaseSelector:  # pragma: no cover - helper implementing a callable selector
    def __init__(self, config):
        self.config = config

    def __call__(self, value):  # Return the provided value without validation.
        return value


class SelectSelectorConfig:  # pragma: no cover - minimal container
    def __init__(self, *, options=None, domain=None, device_class=None, custom_value=False):
        self.options = options or []
        self.domain = domain
        self.device_class = device_class
        self.custom_value = custom_value


class SelectSelector(_BaseSelector):
    pass


class EntitySelectorConfig(SelectSelectorConfig):
    pass


class EntitySelector(_BaseSelector):
    pass


class TextSelectorConfig:  # pragma: no cover - simple container for text selector settings
    def __init__(self, *, type="text", multiline=False, **kwargs):
        self.type = type
        self.multiline = multiline
        for key, value in kwargs.items():
            setattr(self, key, value)


class TextSelector(_BaseSelector):
    pass


selector.SelectSelectorConfig = SelectSelectorConfig
selector.SelectSelector = SelectSelector
selector.EntitySelectorConfig = EntitySelectorConfig
selector.EntitySelector = EntitySelector
selector.TextSelectorConfig = TextSelectorConfig
selector.TextSelector = TextSelector
sys.modules["homeassistant.helpers.selector"] = selector

event = types.ModuleType("homeassistant.helpers.event")


def async_track_time_interval(_hass, _action, _interval):  # pragma: no cover - stub scheduler
    def _cancel():
        return None

    return _cancel


event.async_track_time_interval = async_track_time_interval


def async_track_state_change_event(_hass, _entity_ids, _action):  # pragma: no cover - stub
    def _cancel():
        return None

    return _cancel


event.async_track_state_change_event = async_track_state_change_event
sys.modules["homeassistant.helpers.event"] = event

aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")


def async_get_clientsession(hass):  # pragma: no cover - stubbed
    raise NotImplementedError


aiohttp_client.async_get_clientsession = async_get_clientsession
sys.modules["homeassistant.helpers.aiohttp_client"] = aiohttp_client

util = types.ModuleType("homeassistant.util")


def slugify(value: str) -> str:  # pragma: no cover - simple stub
    if value is None:
        return ""
    text = str(value)
    return "_".join(text.strip().lower().split())


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

    class SensorDeviceClass:
        TEMPERATURE = _SensorClass("temperature")
        HUMIDITY = _SensorClass("humidity")
        ILLUMINANCE = _SensorClass("illuminance")
        MOISTURE = _SensorClass("moisture")
        CO2 = _SensorClass("co2")
        PH = _SensorClass("ph")
        CONDUCTIVITY = _SensorClass("conductivity")

    class SensorEntity:  # pragma: no cover - simple HA stand-in
        """Minimal SensorEntity implementation for local tests."""

        hass = None

        def __init__(self, *_args, **_kwargs) -> None:
            self._attr_should_poll = False

        @property
        def should_poll(self) -> bool:  # pragma: no cover - simple property
            return getattr(self, "_attr_should_poll", False)

        async def async_added_to_hass(self):  # pragma: no cover - stub
            return None

        def async_on_remove(self, func):  # pragma: no cover - stub helper
            return func

        def async_write_ha_state(self):  # pragma: no cover - stub helper
            return None

    class SensorStateClass:  # pragma: no cover - simple enum substitute
        MEASUREMENT = "measurement"
        TOTAL = "total"

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
const.EVENT_HOMEASSISTANT_STARTED = "homeassistant_started"
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
    def __init__(self) -> None:
        self.hass = None

    def async_show_form(
        self,
        *,
        step_id,
        data_schema=None,
        errors=None,
        description_placeholders=None,
    ):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
            "description_placeholders": description_placeholders or {},
        }

    def async_show_menu(self, *, step_id, menu_options, description_placeholders=None):
        return {
            "type": "menu",
            "step_id": step_id,
            "menu_options": menu_options,
            "description_placeholders": description_placeholders or {},
        }

    def async_create_entry(self, *, title="", data=None, options=None):
        return {
            "type": "create_entry",
            "title": title,
            "data": data or {},
            "options": options or {},
        }

    def async_abort(self, *, reason, description_placeholders=None):
        result = {
            "type": "abort",
            "reason": reason,
        }
        if description_placeholders:
            result["description_placeholders"] = description_placeholders
        return result


class ConfigFlow(_BaseFlow):  # pragma: no cover - minimal stub
    def __init_subclass__(cls, *, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.domain = domain

    def _async_current_entries(self):
        if not getattr(self, "hass", None):
            return []

        entries = getattr(self.hass.config_entries, "_entries", {})
        domain = getattr(self, "domain", None)
        return [entry for entry in entries.values() if getattr(entry, "domain", None) == domain]


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


class Store:  # pragma: no cover - minimal persistent store per hass/key
    _STORAGE: dict[int, dict[str, dict[str, object]]] = {}

    def __init__(self, hass, _version, key) -> None:
        hass_store = self._STORAGE.setdefault(id(hass), {})
        self._bucket = hass_store.setdefault(key, {})

    async def async_load(self):
        return deepcopy(self._bucket)

    async def async_save(self, data) -> None:
        self._bucket.clear()
        self._bucket.update(deepcopy(data))


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
    instance = HomeAssistant()
    if instance.helpers is not None:
        instance.helpers.aiohttp_client = aiohttp_client
    return instance


@pytest.fixture
def enable_custom_integrations():
    """Stub fixture for compatibility with Home Assistant tests."""
    yield


@pytest.fixture
def hass_admin_user():
    """Provide a simple stub admin user."""
    return types.SimpleNamespace()
