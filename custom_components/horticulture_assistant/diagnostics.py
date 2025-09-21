from __future__ import annotations

from pathlib import Path
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

    payload["log_tail"] = _read_log_tail(hass, entry)
    return async_redact_data(payload, TO_REDACT)


def _read_log_tail(hass: HomeAssistant, entry) -> list[str]:
    """Return a masked tail of the core log file for quick troubleshooting."""

    log_path = Path(hass.config.path("home-assistant.log"))
    if not log_path.exists():
        return []

    try:
        lines = log_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return []

    tail = lines[-200:]
    api_key = entry.data.get(CONF_API_KEY) or entry.options.get(CONF_API_KEY)
    if not api_key:
        return tail

    secret = str(api_key)
    return [line.replace(secret, "***") for line in tail]
