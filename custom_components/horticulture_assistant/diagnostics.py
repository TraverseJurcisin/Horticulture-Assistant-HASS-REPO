from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_PROFILES, DOMAIN

TO_REDACT = {CONF_API_KEY, "secret", "client_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: dict[str, Any] = {
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "version": entry.version,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "profiles": [],
        "coordinators": {},
    }

    # Profile summaries (if registry has been initialized)
    reg = hass.data.get(DOMAIN, {}).get("profile_registry")
    if reg:
        try:
            data["profiles"] = reg.summaries()
        except Exception:  # pragma: no cover
            pass

    # Coordinator summaries (if present)
    coord_ai = hass.data.get(DOMAIN, {}).get("coordinator_ai")
    coord_local = hass.data.get(DOMAIN, {}).get("coordinator_local")
    coord_prof = hass.data.get(DOMAIN, {}).get("coordinator")

    def _coord_info(c):
        if not c:
            return None
        return {
            "last_update_success": getattr(c, "last_update_success", None),
            "last_update_time": getattr(c, "_last_update_success_time", None),
            "update_interval": str(getattr(c, "update_interval", None)),
        }

    data["coordinators"] = {
        "ai": _coord_info(coord_ai),
        "local": _coord_info(coord_local),
        "profile": _coord_info(coord_prof),
    }

    # Include a small, redacted view of profiles in options for quick debugging
    options_profiles = entry.options.get(CONF_PROFILES, {})
    if options_profiles:
        data["options_profiles"] = list(options_profiles.keys())

    return data
