from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

REDACT = {"api_key", "secret", "client_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), REDACT),
            "options": async_redact_data(dict(entry.options), REDACT),
        },
        "coordinators": {},
        "profiles": [],
    }

    # Pull optional registries/coordinators if set in hass.data
    bag = hass.data.get(DOMAIN, {})
    for key in ("coordinator_ai", "coordinator_local", "coordinator"):
        coord = bag.get(key)
        if coord:
            data["coordinators"][key] = {
                "last_update_success": coord.last_update_success,
                "update_interval": str(getattr(coord, "update_interval", None)),
            }

    reg = bag.get("profile_registry")
    if reg and hasattr(reg, "summaries"):
        try:
            data["profiles"] = reg.summaries()
        except Exception:  # pragma: no cover - defensive
            LOGGER.exception("Failed to summarize profile registry")
            data["profiles"] = []

    return data
