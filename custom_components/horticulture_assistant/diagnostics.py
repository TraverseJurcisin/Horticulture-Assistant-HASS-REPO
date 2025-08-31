from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .utils.redact import redact

LOGGER = logging.getLogger(__name__)

REDACT = {"api_key", "secret", "client_id"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    data: dict[str, Any] = {
        "schema_version": 2,
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "data": redact(dict(entry.data), REDACT),
            "options": redact(dict(entry.options), REDACT),
        },
        "coordinators": {},
        "profile_count": 0,
        "profiles": [],
    }

    # Pull optional registries/coordinators if set in hass.data
    bag: dict[str, Any] = hass.data.get(DOMAIN, {})
    for key in ("coordinator_ai", "coordinator_local", "coordinator"):
        coord = bag.get(key)
        if coord:
            data["coordinators"][key] = {
                "last_update_success": coord.last_update_success,
                "last_update": getattr(coord, "last_update", None),
                "update_interval": str(getattr(coord, "update_interval", None)),
                "last_exception": repr(getattr(coord, "last_exception", None)),
            }

    reg = bag.get("profile_registry")
    if reg and hasattr(reg, "summaries"):
        try:
            data["profiles"] = reg.summaries()
        except Exception:  # pragma: no cover - defensive
            LOGGER.exception("Failed to summarize profile registry")
        data["profile_count"] = len(data["profiles"])

    return data
