import asyncio
import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[3] / "custom_components/horticulture_assistant/__init__.py"
PACKAGE = "custom_components.horticulture_assistant"
if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(Path(__file__).resolve().parents[3] / "custom_components/horticulture_assistant")]
    sys.modules[PACKAGE] = pkg
spec = importlib.util.spec_from_file_location(f"{PACKAGE}.__init__", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
DOMAIN = module.DOMAIN
SERVICE_UPDATE_SENSORS = module.SERVICE_UPDATE_SENSORS

class DummyServices:
    def __init__(self):
        self.registered = []
        self.removed = []
    def async_register(self, domain, name, func):
        self.registered.append((domain, name))
    def has_service(self, domain, name):
        return (domain, name) in self.registered and (domain, name) not in self.removed
    def async_remove(self, domain, name):
        if (domain, name) in self.registered:
            self.registered.remove((domain, name))
        self.removed.append((domain, name))

class DummyConfigEntries:
    def __init__(self, hass):
        self.forwarded = []
        self._hass = hass

    def async_forward_entry_setup(self, entry, platform):
        assert entry.entry_id in self._hass.data[DOMAIN]
        self.forwarded.append((entry, platform))

    async def async_forward_entry_unload(self, entry, platform):
        assert entry.entry_id in self._hass.data[DOMAIN]
        self.forwarded.append((entry, f"unload_{platform}"))
        return True

class DummyConfig:
    def __init__(self, base: Path):
        self._base = base
    def path(self, name: str) -> str:
        return str(self._base / name)

class DummyHass:
    def __init__(self, base: Path):
        self.config = DummyConfig(base)
        self.services = DummyServices()
        self.data = {}
        self.config_entries = DummyConfigEntries(self)
        self.async_create_task = lambda coro: coro  # execute immediately

class DummyEntry:
    def __init__(self, data):
        self.entry_id = "eid123"
        self.data = data

def test_setup_entry(tmp_path: Path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry({"plant_name": "Tomato", "plant_id": "tomato1"})
    asyncio.run(module.async_setup_entry(hass, entry))
    assert entry.entry_id in hass.data[DOMAIN]
    stored = hass.data[DOMAIN][entry.entry_id]
    assert stored["plant_id"] == "tomato1"
    assert stored["plant_name"] == "Tomato"
    assert stored["profile_dir"] == Path(tmp_path / "plants/tomato1")
    assert hass.data[DOMAIN]["by_plant_id"]["tomato1"] is stored
    assert (DOMAIN, SERVICE_UPDATE_SENSORS) in hass.services.registered


def test_service_registered_once(tmp_path: Path):
    hass = DummyHass(tmp_path)
    entry1 = DummyEntry({"plant_name": "Tomato", "plant_id": "tomato1"})
    entry2 = DummyEntry({"plant_name": "Basil", "plant_id": "basil1"})
    asyncio.run(module.async_setup_entry(hass, entry1))
    asyncio.run(module.async_setup_entry(hass, entry2))
    assert hass.services.registered.count((DOMAIN, SERVICE_UPDATE_SENSORS)) == 1


def test_unload_entry(tmp_path: Path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry({"plant_name": "Tomato", "plant_id": "tomato1"})
    asyncio.run(module.async_setup_entry(hass, entry))
    assert entry.entry_id in hass.data[DOMAIN]
    asyncio.run(module.async_unload_entry(hass, entry))
    assert DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]
    domain_data = hass.data.get(DOMAIN, {})
    assert "tomato1" not in domain_data.get("by_plant_id", {})


def test_service_removed_on_last_unload(tmp_path: Path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry({"plant_name": "Tomato", "plant_id": "tomato1"})
    asyncio.run(module.async_setup_entry(hass, entry))
    assert hass.services.has_service(DOMAIN, SERVICE_UPDATE_SENSORS)
    asyncio.run(module.async_unload_entry(hass, entry))
    assert (DOMAIN, SERVICE_UPDATE_SENSORS) in hass.services.removed
