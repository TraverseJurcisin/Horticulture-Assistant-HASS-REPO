from __future__ import annotations

from datetime import datetime

from homeassistant.components.diagnostics import async_redact_data

from .calibration.store import async_load_all as calib_load_all
from .const import DOMAIN
from .profile.store import async_load_all

TO_REDACT = {"api_key", "Authorization"}


async def async_get_config_entry_diagnostics(hass, entry):
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    store = entry_data.get("store")
    ai = entry_data.get("coordinator_ai")
    plants = store.data.get("plants", {}) if store else {}
    zones = store.data.get("zones", {}) if store else {}
    registry = hass.data.get(DOMAIN, {}).get("profile_registry")
    if registry:
        profiles = {p.plant_id: p.to_json() for p in registry}
    else:
        profiles = await async_load_all(hass)
    # Summarize citation provenance across all profiles
    total_citations = 0
    citation_summary: dict[str, int] = {}
    latest: datetime | None = None
    for prof in profiles.values():
        for key, variable in (prof.get("variables") or {}).items():
            cites = variable.get("citations") or []
            if not cites:
                continue
            total_citations += len(cites)
            citation_summary[key] = citation_summary.get(key, 0) + len(cites)
        lr = prof.get("last_resolved")
        if lr:
            ts = datetime.fromisoformat(lr.replace("Z", "+00:00"))
            if latest is None or ts > latest:
                latest = ts
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
        "profiles": profiles,
        "citations_count": total_citations,
        "citations_summary": citation_summary,
        "last_resolved_utc": latest.isoformat() if latest else None,
        "calibrations": await calib_load_all(hass),
    }
    return async_redact_data(data, TO_REDACT)
