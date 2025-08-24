import pytest
from homeassistant.helpers import issue_registry as ir

from custom_components.horticulture_assistant.const import DOMAIN
from custom_components.horticulture_assistant.entity_utils import ensure_entities_exist

pytestmark = pytest.mark.asyncio


async def test_missing_entities_create_issue(hass):
    ensure_entities_exist(hass, "plant1", ["sensor.missing"])
    await hass.async_block_till_done()
    issues = ir.async_get(hass).issues
    assert (DOMAIN, "missing_entity_plant1") in issues


async def test_existing_entities_no_issue(hass):
    hass.states.async_set("sensor.ok", 1)
    ensure_entities_exist(hass, "plant1", ["sensor.ok", "", None])
    await hass.async_block_till_done()
    issues = ir.async_get(hass).issues
    assert (DOMAIN, "missing_entity_plant1") not in issues
