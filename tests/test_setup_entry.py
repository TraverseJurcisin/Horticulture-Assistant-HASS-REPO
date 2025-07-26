import asyncio
import importlib.util
import sys
import types
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant/__init__.py"
PACKAGE = "custom_components.horticulture_assistant"
if PACKAGE not in sys.modules:
    pkg = types.ModuleType(PACKAGE)
    pkg.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/horticulture_assistant")]
    sys.modules[PACKAGE] = pkg
spec = importlib.util.spec_from_file_location(f"{PACKAGE}.__init__", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
DOMAIN = module.DOMAIN

class DummyServices:
    def __init__(self):
        self.registered = []
    def async_register(self, domain, name, func):
        self.registered.append((domain, name))

class DummyConfigEntries:
    def __init__(self):
        self.forwarded = []
    def async_forward_entry_setup(self, entry, platform):
        self.forwarded.append((entry, platform))
    async def async_forward_entry_unload(self, entry, platform):
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
        self.config_entries = DummyConfigEntries()
        self.async_create_task = lambda *a, **k: None
        self.data = {}

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
    assert (DOMAIN, "update_sensors") in hass.services.registered


def test_unload_entry(tmp_path: Path):
    hass = DummyHass(tmp_path)
    entry = DummyEntry({"plant_name": "Tomato", "plant_id": "tomato1"})
    asyncio.run(module.async_setup_entry(hass, entry))
    assert entry.entry_id in hass.data[DOMAIN]
    asyncio.run(module.async_unload_entry(hass, entry))
    assert entry.entry_id not in hass.data[DOMAIN]
