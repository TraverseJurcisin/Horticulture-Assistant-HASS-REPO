"""Config entry flow smoke tests for UI setup support."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.horticulture_assistant import config_flow as cfg

DOMAIN = "horticulture_assistant"


def _prepare_flow(flow, hass, *, abort_on_unique_ids=None):
    """Attach missing Home Assistant helpers to the flow stub."""

    abort_on_unique_ids = abort_on_unique_ids or set()

    if not hasattr(hass, "config"):
        hass.config = SimpleNamespace(location_name="Horticulture Assistant")  # type: ignore[attr-defined]
    elif not getattr(hass.config, "location_name", None):
        hass.config.location_name = "Horticulture Assistant"

    state: dict[str, bool] = {"abort_called": False, "aborted": False}

    async def _set_unique_id(unique_id, **kwargs):
        flow._unique_id = unique_id

    flow.context = {}
    flow.async_set_unique_id = AsyncMock(side_effect=_set_unique_id)  # type: ignore[attr-defined]

    def _abort_if_unique_id_configured(*_, **__):
        state["abort_called"] = True
        if getattr(flow, "_unique_id", None) in abort_on_unique_ids:
            state["aborted"] = True
            return {"type": "abort", "reason": "already_configured"}
        return None

    flow._abort_if_unique_id_configured = _abort_if_unique_id_configured  # type: ignore[attr-defined]

    return state


@pytest.mark.asyncio
async def test_user_step_shows_initial_form(hass):
    """Ensure the config flow presents the initial UI step."""

    flow = cfg.ConfigFlow()
    flow.hass = hass
    _prepare_flow(flow, hass)

    result = await flow.async_step_user()

    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_user_step_skip_creates_entry(hass):
    """Verify skipping profile creation creates a config entry."""

    flow = cfg.ConfigFlow()
    flow.hass = hass
    _prepare_flow(flow, hass)

    await flow.async_step_user()
    result = await flow.async_step_user({"setup_mode": "skip"})

    assert result["type"] == "create_entry"
    assert result["data"] == {}
    assert result["options"] == {}


@pytest.mark.asyncio
async def test_duplicate_flow_marks_abort(hass):
    """Ensure duplicate config flows trigger the unique ID guard."""

    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    flow = cfg.ConfigFlow()
    flow.hass = hass
    state = _prepare_flow(flow, hass, abort_on_unique_ids={DOMAIN})

    await flow.async_step_user()

    assert state["abort_called"] is True
    assert state["aborted"] is True


@pytest.mark.asyncio
async def test_import_flow_delegates_to_user(hass):
    """Confirm YAML imports reuse the user step to create an entry."""

    flow = cfg.ConfigFlow()
    flow.hass = hass
    _prepare_flow(flow, hass)
    flow.context = {"source": "import"}

    result = await flow.async_step_import({"setup_mode": "skip"})

    assert result["type"] == "create_entry"
    assert result["data"] == {}
    assert result["options"] == {}


@pytest.mark.asyncio
async def test_import_flow_preserves_payload(hass):
    """Confirm YAML imports store provided configuration payload."""

    flow = cfg.ConfigFlow()
    flow.hass = hass
    _prepare_flow(flow, hass)
    flow.context = {"source": "import"}

    payload = {"title": "My Garden", "base_url": "http://example"}
    result = await flow.async_step_import(payload)

    assert result["type"] == "create_entry"
    assert result["title"] == "My Garden"
    assert result["data"] == {"base_url": "http://example"}
    assert result["options"] == {}
