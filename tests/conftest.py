import asyncio
import sys
import types
from pathlib import Path

import pytest

try:  # Home Assistant available: rely on real fixtures
    import homeassistant  # noqa: F401
except Exception:
    # Minimal Home Assistant stand-ins so tests run without the real package
    ha_pkg = types.ModuleType("homeassistant")
    ha_pkg.__path__ = []
    sys.modules.setdefault("homeassistant", ha_pkg)

    core = types.ModuleType("homeassistant.core")

    class HomeAssistant:  # pragma: no cover - simple stub
        def __init__(self) -> None:
            self.config = types.SimpleNamespace(
                components=set(), path=lambda *p: str(Path("/tmp").joinpath(*p))
            )
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
    sys.modules.setdefault("homeassistant.core", core)

    helpers = types.ModuleType("homeassistant.helpers")
    helpers.__path__ = []
    sys.modules.setdefault("homeassistant.helpers", helpers)

    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")

    def async_get_clientsession(hass):  # pragma: no cover - stubbed
        raise NotImplementedError

    aiohttp_client.async_get_clientsession = async_get_clientsession
    sys.modules.setdefault("homeassistant.helpers.aiohttp_client", aiohttp_client)

    util = types.ModuleType("homeassistant.util")

    def slugify(value: str) -> str:  # pragma: no cover - simple stub
        return value

    util.slugify = slugify
    sys.modules.setdefault("homeassistant.util", util)

    const = types.ModuleType("homeassistant.const")
    const.Platform = types.SimpleNamespace(
        SENSOR="sensor", BINARY_SENSOR="binary_sensor", SWITCH="switch", NUMBER="number"
    )
    sys.modules.setdefault("homeassistant.const", const)

    config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:  # pragma: no cover - minimal stub
        def __init__(self, entry_id: str = "", data=None, options=None, title: str = "") -> None:
            self.entry_id = entry_id
            self.data = data or {}
            self.options = options or {}
            self.title = title

    config_entries.ConfigEntry = ConfigEntry
    sys.modules.setdefault("homeassistant.config_entries", config_entries)

    entity = types.ModuleType("homeassistant.helpers.entity")

    class EntityCategory:  # pragma: no cover - minimal stub
        CONFIG = "config"
        DIAGNOSTIC = "diagnostic"

    entity.EntityCategory = EntityCategory
    sys.modules.setdefault("homeassistant.helpers.entity", entity)

    storage = types.ModuleType("homeassistant.helpers.storage")

    class Store:  # pragma: no cover - minimal in-memory store
        def __init__(self, _hass, _version, _key) -> None:
            self.data: dict[str, object] = {}

        async def async_load(self):
            return self.data

        async def async_save(self, data) -> None:
            self.data = data

    storage.Store = Store
    sys.modules.setdefault("homeassistant.helpers.storage", storage)

    @pytest.fixture
    def hass() -> HomeAssistant:
        """Provide a minimal Home Assistant instance."""
        return HomeAssistant()

    @pytest.fixture
    def enable_custom_integrations():
        """Stub fixture for compatibility with Home Assistant tests."""
        yield
