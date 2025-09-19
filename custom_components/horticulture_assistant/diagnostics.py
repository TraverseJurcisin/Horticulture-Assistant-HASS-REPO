from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_API_KEY, DOMAIN
from .profile_registry import ProfileRegistry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data.get(DOMAIN, {})
    reg: ProfileRegistry | None = data.get("registry")
    payload: dict[str, Any] = {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
            "options": {key: ("***" if key == CONF_API_KEY else value) for key, value in entry.options.items()},
        },
        "profile_count": 0,
        "profiles": [],
        "coordinators": {},
        "schema_version": 2,
    }
    if reg:
        profiles = reg.summaries()
        payload["profiles"] = profiles
        payload["profile_count"] = len(profiles)
    for key, coord in data.items():
        if not key.startswith("coordinator"):
            continue
        payload["coordinators"][key] = {
            "last_update_success": getattr(coord, "last_update_success", False),
            "last_update": getattr(coord, "last_update", None),
            "last_exception": getattr(coord, "last_exception", None),
        }
    return async_redact_data(payload, TO_REDACT)
