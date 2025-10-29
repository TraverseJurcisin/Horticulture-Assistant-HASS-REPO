from __future__ import annotations

import types
from unittest.mock import AsyncMock

import pytest

from custom_components.horticulture_assistant import services as services_module


class DummyStates:
    def __init__(self, states: dict[str, object]) -> None:
        self._states = states

    def get(self, entity_id: str) -> object | None:
        return self._states.get(entity_id)


class DummyState:
    def __init__(self, **attrs: object) -> None:
        self.attributes = attrs


class DummyServices:
    def __init__(self) -> None:
        self._registered: dict[tuple[str, str], object] = {}

    def async_register(self, domain: str, service: str, handler, schema=None, **_kwargs) -> None:
        self._registered[(domain, service)] = handler

    def has_service(self, *_args, **_kwargs) -> bool:
        return False


class DummyConfigEntries:
    def async_update_entry(self, entry, *, options) -> None:  # pragma: no cover - trivial
        entry.options = options


@pytest.mark.asyncio
async def test_replace_sensor_allows_entities_missing_registry(monkeypatch):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.temp": DummyState(device_class="temperature", unit_of_measurement="°C"),
            }
        ),
        services=DummyServices(),
        config_entries=DummyConfigEntries(),
    )
    entry = types.SimpleNamespace(entry_id="abc", options={services_module.CONF_PROFILES: {"plant": {"sensors": {}}}})
    registry = types.SimpleNamespace(async_replace_sensor=AsyncMock())
    store = types.SimpleNamespace(data=None, save=AsyncMock())

    empty_registry = types.SimpleNamespace(
        async_get=lambda _entity_id: None,
        async_get_entity_id=lambda *_args, **_kwargs: None,
    )
    entity_registry = types.SimpleNamespace(async_get=lambda _hass: empty_registry)
    monkeypatch.setattr(services_module, "er", entity_registry)
    monkeypatch.setattr(services_module, "cv", types.SimpleNamespace(entity_id=lambda value: value))

    await services_module.async_register_all(
        hass,
        entry,
        ai_coord=None,
        local_coord=None,
        profile_coord=None,
        registry=registry,
        store=store,
    )

    handler = hass.services._registered[(services_module.DOMAIN, services_module.SERVICE_REPLACE_SENSOR)]
    call = types.SimpleNamespace(data={"profile_id": "plant", "measurement": "temperature", "entity_id": "sensor.temp"})

    await handler(call)

    registry.async_replace_sensor.assert_awaited_once_with("plant", "temperature", "sensor.temp")


@pytest.mark.asyncio
async def test_link_sensor_allows_entities_missing_registry(monkeypatch):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.light": DummyState(device_class="illuminance", unit_of_measurement="lx"),
            }
        ),
        services=DummyServices(),
        config_entries=DummyConfigEntries(),
    )
    entry = types.SimpleNamespace(entry_id="abc", options={services_module.CONF_PROFILES: {"plant": {"sensors": {}}}})
    registry = types.SimpleNamespace(async_replace_sensor=AsyncMock())
    store = types.SimpleNamespace(data=None, save=AsyncMock())

    empty_registry = types.SimpleNamespace(
        async_get=lambda _entity_id: None,
        async_get_entity_id=lambda *_args, **_kwargs: None,
    )
    entity_registry = types.SimpleNamespace(async_get=lambda _hass: empty_registry)
    monkeypatch.setattr(services_module, "er", entity_registry)
    monkeypatch.setattr(services_module, "cv", types.SimpleNamespace(entity_id=lambda value: value))

    await services_module.async_register_all(
        hass,
        entry,
        ai_coord=None,
        local_coord=None,
        profile_coord=None,
        registry=registry,
        store=store,
    )

    handler = hass.services._registered[(services_module.DOMAIN, services_module.SERVICE_LINK_SENSOR)]
    call = types.SimpleNamespace(data={"profile_id": "plant", "role": "illuminance", "entity_id": "sensor.light"})

    await handler(call)

    registry.async_replace_sensor.assert_awaited_once_with("plant", "illuminance", "sensor.light")


@pytest.mark.asyncio
async def test_update_sensors_service_handles_extended_roles(monkeypatch):
    hass = types.SimpleNamespace(
        states=DummyStates(
            {
                "sensor.co2": DummyState(device_class="carbon_dioxide"),
                "sensor.ph": DummyState(device_class="ph"),
            }
        ),
        services=DummyServices(),
        config_entries=DummyConfigEntries(),
        async_create_task=lambda coro: coro,
        async_block_till_done=AsyncMock(),
    )
    entry = types.SimpleNamespace(
        entry_id="abc",
        options={services_module.CONF_PROFILES: {"plant": {"sensors": {}}}},
    )
    registry = types.SimpleNamespace(
        async_link_sensors=AsyncMock(),
        publish_full_snapshot=lambda: None,
    )
    store = types.SimpleNamespace(data=None, save=AsyncMock())

    monkeypatch.setattr(
        services_module,
        "validate_sensor_links",
        lambda _hass, _sensors: types.SimpleNamespace(errors=[], warnings=[]),
    )
    monkeypatch.setattr(services_module, "cv", types.SimpleNamespace(entity_id=lambda value: value))

    await services_module.async_register_all(
        hass,
        entry,
        ai_coord=None,
        local_coord=None,
        profile_coord=None,
        registry=registry,
        store=store,
    )

    handler = hass.services._registered[(services_module.DOMAIN, services_module.SERVICE_UPDATE_SENSORS)]
    call = types.SimpleNamespace(data={"profile_id": "plant", "co2": "sensor.co2", "ph": "sensor.ph"})

    await handler(call)

    registry.async_link_sensors.assert_awaited_once_with("plant", {"co2": "sensor.co2", "ph": "sensor.ph"})
