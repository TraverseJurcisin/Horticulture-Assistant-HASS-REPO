from __future__ import annotations

import numpy as np

from .fit import eval_model
from .store import async_get_for_entity


async def lux_to_ppfd(hass, lux_entity_id: str, lux_value: float) -> float | None:
    rec = await async_get_for_entity(hass, lux_entity_id)
    if not rec:
        return None
    model = rec["model"]["model"]
    coeffs: list[float] = rec["model"]["coefficients"]
    return float(eval_model(model, coeffs, np.array([lux_value]))[0])
