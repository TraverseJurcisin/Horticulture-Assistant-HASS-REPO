from __future__ import annotations
from homeassistant.components.diagnostics import async_redact_data

TO_REDACT = {"api_key", "Authorization"}

async def async_get_config_entry_diagnostics(hass, entry):
    data = {
        "options": dict(entry.options),
        "data": {k: ("***" if "key" in k.lower() else v) for k, v in entry.data.items()},
        "entities": [e.entity_id for e in hass.states.async_all() if e.entity_id.startswith("sensor.horticulture_assistant")],
    }
    return async_redact_data(data, TO_REDACT)
