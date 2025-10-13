import importlib.util
from pathlib import Path
import types

import pytest


SPEC = importlib.util.spec_from_file_location(
    "horticulture_storage",
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "horticulture_assistant"
    / "storage.py",
)
assert SPEC and SPEC.loader  # narrow type check for mypy/static analysers
storage = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(storage)


class DummyStore:
    def __init__(self, hass, version, key) -> None:  # noqa: D401 - signature mirrors Store
        self._data = {
            "recipes": ["tea"],
            "inventory": {"nutrients": 1},
        }

    async def async_load(self):
        return dict(self._data)

    async def async_save(self, data):  # pragma: no cover - not used in this test
        self._data = data


@pytest.mark.asyncio
async def test_local_store_load_merges_defaults(monkeypatch):
    monkeypatch.setattr(storage, "Store", DummyStore)

    hass = types.SimpleNamespace()
    store = storage.LocalStore(hass)

    data = await store.load()

    assert data["recipes"] == ["tea"]
    assert data["inventory"] == {"nutrients": 1}
    for key in storage.DEFAULT_DATA:
        assert key in data
