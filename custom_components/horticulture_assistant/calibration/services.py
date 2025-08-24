from __future__ import annotations

import asyncio
import logging
import math
import uuid
from typing import Any

import numpy as np

try:  # pragma: no cover - allow import without Home Assistant
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.exceptions import HomeAssistantError
except Exception:  # pragma: no cover
    HomeAssistant = Any  # type: ignore
    ServiceCall = Any  # type: ignore

from .fit import fit_linear, fit_power, fit_quadratic
from .schema import CalibrationModel, CalibrationPoint, CalibrationRecord
from .session import CalibrationSession, LivePoint, now_iso
from .store import async_save_for_entity

_LOGGER = logging.getLogger(__name__)

_SESSIONS: dict[str, CalibrationSession] = {}


async def _avg_entity(hass: HomeAssistant, entity_id: str, seconds: int) -> float:
    samples: list[float] = []
    for _ in range(max(1, seconds)):
        state = hass.states.get(entity_id)
        try:
            val = float(state.state)  # type: ignore[union-attr]
            if math.isnan(val) or val < 0:
                raise ValueError
            samples.append(val)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(1)
    if not samples:
        raise HomeAssistantError(f"no valid readings from {entity_id}")
    return float(sum(samples) / len(samples))


async def _handle_start(hass: HomeAssistant, call: ServiceCall) -> None:
    session_id = uuid.uuid4().hex
    session = CalibrationSession(
        session_id=session_id,
        lux_entity_id=call.data["lux_entity_id"],
        ppfd_entity_id=call.data.get("ppfd_entity_id"),
        model=call.data.get("model", "linear"),
        averaging_seconds=call.data.get("averaging_seconds", 3),
        notes=call.data.get("notes"),
    )
    _SESSIONS[session_id] = session
    hass.bus.async_fire("horticulture_assistant_calibration_started", {"session_id": session_id})
    _LOGGER.info("Started calibration session %s", session_id)
    return {"session_id": session_id}


async def _handle_add_point(hass: HomeAssistant, call: ServiceCall) -> None:
    session = _SESSIONS.get(call.data["session_id"])
    if not session:
        raise HomeAssistantError("unknown session")
    lux = await _avg_entity(hass, session.lux_entity_id, session.averaging_seconds)
    if session.ppfd_entity_id:
        ppfd = await _avg_entity(hass, session.ppfd_entity_id, session.averaging_seconds)
    else:
        if "ppfd_value" not in call.data:
            raise HomeAssistantError("ppfd_value required")
        ppfd = float(call.data["ppfd_value"])
        if ppfd <= 0:
            raise HomeAssistantError("invalid ppfd value")
    session.points.append(LivePoint(lux, ppfd, now_iso()))
    hass.bus.async_fire(
        "horticulture_assistant_calibration_update",
        {"session_id": session.session_id, "n": len(session.points)},
    )


async def _handle_finish(hass: HomeAssistant, call: ServiceCall) -> None:
    session = _SESSIONS.pop(call.data["session_id"], None)
    if not session:
        raise HomeAssistantError("unknown session")
    if len(session.points) < 5:
        raise HomeAssistantError("need at least 5 points")
    lux = np.array([p.lux for p in session.points], dtype=float)
    ppfd = np.array([p.ppfd for p in session.points], dtype=float)
    fit = {
        "linear": fit_linear,
        "quadratic": fit_quadratic,
        "power": fit_power,
    }.get(session.model)
    if not fit:
        raise HomeAssistantError("unknown model")
    coeffs, r2, rmse = fit(lux, ppfd)
    record = CalibrationRecord(
        lux_entity_id=session.lux_entity_id,
        device_id=None,
        model=CalibrationModel(
            model=session.model,
            coefficients=coeffs,
            r2=r2,
            rmse=rmse,
            n=len(session.points),
            lux_min=float(lux.min()),
            lux_max=float(lux.max()),
            notes=session.notes,
        ),
        points=[CalibrationPoint(p.lux, p.ppfd, p.at_utc) for p in session.points],
    )
    await async_save_for_entity(hass, session.lux_entity_id, record.to_json())
    hass.bus.async_fire(
        "horticulture_assistant_calibration_done",
        {
            "session_id": session.session_id,
            "r2": r2,
            "rmse": rmse,
            "n": len(session.points),
        },
    )
    if len(session.points) < 5 or r2 < 0.9:
        _LOGGER.warning(
            "Calibration quality low: n=%s r2=%.3f rmse=%.3f",
            len(session.points),
            r2,
            rmse,
        )
    _LOGGER.info(
        "Stored calibration for %s: model=%s coeffs=%s r2=%.3f rmse=%.3f",
        session.lux_entity_id,
        session.model,
        coeffs,
        r2,
        rmse,
    )


async def _handle_abort(hass: HomeAssistant, call: ServiceCall) -> None:
    session = _SESSIONS.pop(call.data["session_id"], None)
    if session:
        hass.bus.async_fire(
            "horticulture_assistant_calibration_aborted",
            {"session_id": session.session_id},
        )


async def async_setup(hass: HomeAssistant) -> None:
    hass.services.async_register(
        "horticulture_assistant",
        "start_calibration",
        lambda call: _handle_start(hass, call),
    )
    hass.services.async_register(
        "horticulture_assistant",
        "add_calibration_point",
        lambda call: _handle_add_point(hass, call),
    )
    hass.services.async_register(
        "horticulture_assistant",
        "finish_calibration",
        lambda call: _handle_finish(hass, call),
    )
    hass.services.async_register(
        "horticulture_assistant",
        "abort_calibration",
        lambda call: _handle_abort(hass, call),
    )
