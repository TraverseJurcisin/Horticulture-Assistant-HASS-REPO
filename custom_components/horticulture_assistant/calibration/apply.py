from __future__ import annotations

from ..engine.metrics import lux_model_ppfd
from .store import async_get_for_entity


async def lux_to_ppfd(hass, lux_entity_id: str, lux_value: float) -> float | None:
    rec = await async_get_for_entity(hass, lux_entity_id)
    if not rec:
        return None
    model = rec["model"]
    return lux_model_ppfd(model["model"], model["coefficients"], lux_value)
