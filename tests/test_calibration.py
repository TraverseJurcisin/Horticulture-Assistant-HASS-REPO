from types import SimpleNamespace

import numpy as np
import pytest

from custom_components.horticulture_assistant.calibration import services as calib_services
from custom_components.horticulture_assistant.calibration.apply import lux_to_ppfd
from custom_components.horticulture_assistant.calibration.fit import (
    fit_linear,
    fit_power,
)
from custom_components.horticulture_assistant.calibration.store import (
    async_get_for_entity,
    async_save_for_entity,
)


@pytest.mark.asyncio
async def test_linear_fit_accuracy():
    lux = np.linspace(0, 1000, 20)
    ppfd = 0.02 * lux + 5
    coeffs, r2, _ = fit_linear(lux, ppfd)
    assert r2 > 0.98
    assert coeffs[0] == pytest.approx(0.02, rel=0.05)
    assert coeffs[1] == pytest.approx(5, rel=0.1)


@pytest.mark.asyncio
async def test_power_fit_accuracy():
    lux = np.linspace(1, 1000, 20)
    ppfd = 3 * (lux**0.8)
    coeffs, r2, _ = fit_power(lux, ppfd)
    assert r2 > 0.98
    assert coeffs[0] == pytest.approx(3, rel=0.1)
    assert coeffs[1] == pytest.approx(0.8, rel=0.05)


@pytest.mark.asyncio
async def test_store_roundtrip(hass):
    import asyncio

    def _create_task(coro, *_args, **_kwargs):
        return asyncio.create_task(coro)

    hass.async_create_task = _create_task
    from custom_components.horticulture_assistant.calibration import store as store_mod

    class DummyStore:
        def __init__(self):
            self.data = {}

        async def async_load(self):
            return self.data

        async def async_save(self, data):
            self.data = data

    dummy = DummyStore()

    store_mod._store = lambda _hass: dummy
    record = {
        "lux_entity_id": "sensor.lux",
        "device_id": None,
        "model": {
            "model": "linear",
            "coefficients": [2.0, 0.0],
            "r2": 1.0,
            "rmse": 0.0,
            "n": 1,
            "lux_min": 0.0,
            "lux_max": 100.0,
        },
        "points": [],
    }
    await async_save_for_entity(hass, "sensor.lux", record)
    loaded = await async_get_for_entity(hass, "sensor.lux")
    assert loaded == record


@pytest.mark.asyncio
async def test_apply_mapping(hass):
    import asyncio

    def _create_task(coro, *_args, **_kwargs):
        return asyncio.create_task(coro)

    hass.async_create_task = _create_task
    from custom_components.horticulture_assistant.calibration import store as store_mod

    class DummyStore:
        def __init__(self):
            self.data = {}

        async def async_load(self):
            return self.data

        async def async_save(self, data):
            self.data = data

    dummy = DummyStore()
    store_mod._store = lambda _hass: dummy
    record = {
        "lux_entity_id": "sensor.lux",
        "device_id": None,
        "model": {
            "model": "linear",
            "coefficients": [2.0, 0.0],
            "r2": 1.0,
            "rmse": 0.0,
            "n": 1,
            "lux_min": 0.0,
            "lux_max": 100.0,
        },
        "points": [],
    }
    await async_save_for_entity(hass, "sensor.lux", record)
    val = await lux_to_ppfd(hass, "sensor.lux", 50.0)
    assert val == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_services_session_flow(hass):
    import asyncio

    def _create_task(coro, *_args, **_kwargs):
        return asyncio.create_task(coro)

    hass.async_create_task = _create_task
    from custom_components.horticulture_assistant.calibration import store as store_mod

    class DummyStore:
        def __init__(self):
            self.data = {}

        async def async_load(self):
            return self.data

        async def async_save(self, data):
            self.data = data

    dummy = DummyStore()
    store_mod._store = lambda _hass: dummy

    class _States:
        def __init__(self):
            self._data = {}

        def get(self, entity_id):
            return self._data.get(entity_id)

        def async_set(self, entity_id, value):
            self._data[entity_id] = SimpleNamespace(state=value)

    hass.states = _States()
    hass.bus = SimpleNamespace(async_fire=lambda *args, **kwargs: None)

    hass.states.async_set("sensor.lux", 100.0)
    hass.states.async_set("sensor.ppfd", 50.0)
    res = await calib_services._handle_start(
        hass,
        SimpleNamespace(data={"lux_entity_id": "sensor.lux", "ppfd_entity_id": "sensor.ppfd"}),
    )
    session_id = res["session_id"]
    for _ in range(5):
        await calib_services._handle_add_point(hass, SimpleNamespace(data={"session_id": session_id}))
    await calib_services._handle_finish(hass, SimpleNamespace(data={"session_id": session_id}))
    rec = await async_get_for_entity(hass, "sensor.lux")
    assert rec is not None
