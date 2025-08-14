from __future__ import annotations

from typing import Iterable
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from .const import DOMAIN


def ensure_entities_exist(hass: HomeAssistant, plant_id: str, entity_ids: Iterable[str]) -> None:
    missing = [eid for eid in entity_ids if hass.states.get(eid) is None]
    if not missing:
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"missing_entity_{plant_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="missing_entity",
        translation_placeholders={"plant_id": plant_id},
    )
