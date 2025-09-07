from __future__ import annotations

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


async def async_register(system_health: system_health.SystemHealthRegistration, hass: HomeAssistant) -> None:
    """Register system health info callback."""

    @callback
    def info_callback(_):
        data = hass.data.get(DOMAIN, {})
        registry = data.get("registry")
        coordinators = [key for key in ("coordinator_ai", "coordinator_local", "coordinator") if key in data]
        return {
            "profiles_loaded": len(registry.list_profiles()) if registry else 0,
            "coordinators": coordinators,
        }

    system_health.register_info(DOMAIN, info_callback)
