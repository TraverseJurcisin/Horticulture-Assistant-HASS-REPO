from __future__ import annotations

from collections.abc import Mapping

from homeassistant.components import system_health
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


async def async_register(system_health: system_health.SystemHealthRegistration, hass: HomeAssistant) -> None:
    """Register system health info callback."""

    @callback
    def info_callback(_):
        domain_data = hass.data.get(DOMAIN, {})
        entry_data = [value for value in domain_data.values() if isinstance(value, Mapping) and "config_entry" in value]

        profiles_loaded = 0
        for data in entry_data:
            registry = data.get("profile_registry") or data.get("profiles") or data.get("registry")
            if registry and hasattr(registry, "list_profiles"):
                try:
                    profiles = registry.list_profiles()
                except Exception:  # pragma: no cover - defensive fallback
                    profiles = []
                if hasattr(profiles, "__len__"):
                    profiles_loaded += len(profiles)

        coordinators = sorted(
            {
                coordinator
                for data in entry_data
                for coordinator in ("coordinator_ai", "coordinator_local", "coordinator")
                if coordinator in data
            }
        )
        return {
            "profiles_loaded": profiles_loaded,
            "coordinators": coordinators,
        }

    system_health.register_info(DOMAIN, info_callback)
