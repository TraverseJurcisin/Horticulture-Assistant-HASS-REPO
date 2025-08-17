from __future__ import annotations

from typing import Iterable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN


def ensure_entities_exist(
    hass: HomeAssistant,
    plant_id: str,
    entity_ids: Iterable[str],
    *,
    translation_key: str = "missing_entity",
    placeholders: dict[str, str] | None = None,
) -> None:
    """Create a repairs issue when referenced entities are missing."""
    missing = [eid for eid in entity_ids if eid and hass.states.get(eid) is None]
    if not missing:
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"missing_entity_{plant_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=translation_key,
        translation_placeholders=placeholders or {"plant_id": plant_id},
    )
