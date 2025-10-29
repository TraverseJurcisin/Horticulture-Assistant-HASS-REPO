import importlib.util
import types
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "horticulture_storage",
    Path(__file__).resolve().parents[1] / "custom_components" / "horticulture_assistant" / "storage.py",
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


class EmptyStore:
    def __init__(self, hass, version, key) -> None:  # noqa: D401 - signature mirrors Store
        self._data = None

    async def async_load(self):
        return self._data

    async def async_save(self, data):  # pragma: no cover - not needed here
        self._data = data


@pytest.mark.asyncio
async def test_local_store_defaults_are_isolated(monkeypatch):
    monkeypatch.setattr(storage, "Store", EmptyStore)

    hass = types.SimpleNamespace()
    store = storage.LocalStore(hass)

    data = await store.load()
    data["inventory"]["foo"] = 42

    assert storage.DEFAULT_DATA["inventory"] == {}

    store_again = storage.LocalStore(hass)
    data_again = await store_again.load()

    assert data_again["inventory"] == {}


class CorruptStore:
    def __init__(self, hass, version, key) -> None:  # noqa: D401 - signature mirrors Store
        self._data = {
            "recipes": None,
            "inventory": [],
            "history": "bad",
            "plants": None,
            "profile": (),
            "recommendation": None,
            "zones": "invalid",
        }

    async def async_load(self):
        return dict(self._data)

    async def async_save(self, data):  # pragma: no cover - not needed here
        self._data = data


@pytest.mark.asyncio
async def test_local_store_load_recovers_from_invalid_types(monkeypatch):
    monkeypatch.setattr(storage, "Store", CorruptStore)

    hass = types.SimpleNamespace()
    store = storage.LocalStore(hass)

    data = await store.load()

    assert data["recipes"] == []
    assert data["inventory"] == {}
    assert data["history"] == []
    assert data["plants"] == {}
    assert data["profile"] == {}
    assert data["recommendation"] == ""
    assert data["zones"] == {}


class NonMappingStore:
    def __init__(self, hass, version, key) -> None:  # noqa: D401 - signature mirrors Store
        self._data = ["not", "a", "mapping"]

    async def async_load(self):
        return list(self._data)

    async def async_save(self, data):  # pragma: no cover - not needed here
        self._data = data


@pytest.mark.asyncio
async def test_local_store_load_resets_on_non_mapping(monkeypatch):
    monkeypatch.setattr(storage, "Store", NonMappingStore)

    hass = types.SimpleNamespace()
    store = storage.LocalStore(hass)

    data = await store.load()

    assert data == storage.DEFAULT_DATA
    assert data is not storage.DEFAULT_DATA
    assert data["history"] is not storage.DEFAULT_DATA["history"]
