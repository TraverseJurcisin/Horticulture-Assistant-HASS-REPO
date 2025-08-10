from __future__ import annotations
from homeassistant.components.diagnostics import async_redact_data
from .const import DOMAIN

TO_REDACT = {"api_key", "Authorization"}

async def async_get_config_entry_diagnostics(hass, entry):
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    store = entry_data.get("store")
    ai = entry_data.get("coordinator_ai")
    plants = store.data.get("plants", {}) if store else {}
    zones = store.data.get("zones", {}) if store else {}
    data = {
        "options": dict(entry.options),
        "data": dict(entry.data),
        "entities": [
            e.entity_id
            for e in hass.states.async_all()
            if e.entity_id.startswith("sensor.horticulture_assistant")
        ],
        "plant_count": len(plants),
        "zone_count": len(zones),
        "last_profile_load": store.data.get("profile", {}).get("loaded_at") if store else None,
        "last_ai_call": ai.last_call.isoformat() if ai and ai.last_call else None,
        "last_ai_exception": ai.last_exception_msg if ai else None,
        "ai_retry_count": ai.retry_count if ai else None,
        "ai_breaker_open": ai.breaker_open if ai else None,
        "ai_latency_ms": ai.latency_ms if ai else None,
    }
    return async_redact_data(data, TO_REDACT)
