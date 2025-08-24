import sys
import types

import pytest

# Create minimal Home Assistant package structure for tests.
ha_pkg = types.ModuleType("homeassistant")
ha_pkg.__path__ = []  # mark as package
sys.modules.setdefault("homeassistant", ha_pkg)

core = types.ModuleType("homeassistant.core")


class HomeAssistant:  # pragma: no cover - simple stub
    def __init__(self) -> None:
        self.config = types.SimpleNamespace(components=set())
        # Populate common Home Assistant attributes accessed by the integration.
        self.data: dict[str, object] = {"integrations": {}}
        self.auth = types.SimpleNamespace()


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
