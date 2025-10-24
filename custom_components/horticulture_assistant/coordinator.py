from __future__ import annotations

import logging
from collections import Counter, deque
from contextlib import suppress
from datetime import datetime, timedelta
from statistics import fmean
from typing import Any

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import CONF_PROFILES, DOMAIN
from .engine.metrics import (
    accumulate_dli,
    dew_point_c,
    lux_to_ppfd,
    mold_risk,
    profile_status,
    vpd_kpa,
)

_LOGGER = logging.getLogger(__name__)


class HorticultureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central data coordinator for plant profile metrics."""

    def __init__(self, hass: HomeAssistant, entry_id: str, options: dict[str, Any]) -> None:
        self._entry_id = entry_id
        self._options = options
        self._dli_totals: dict[str, float] = {}
        self._vpd_history: dict[str, deque[tuple[datetime, float]]] = {}
        self._last_reset: dt_util.date | None = None

        interval = int(options.get("update_interval", 5))

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{entry_id}",
            update_interval=timedelta(minutes=interval),
        )

    async def async_reset_dli(self, profile_id: str | None = None) -> None:
        """Reset accumulated DLI totals for a profile or all profiles."""

        if profile_id is None:
            self._dli_totals.clear()
        else:
            self._dli_totals.pop(profile_id, None)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            profiles: dict[str, Any] = self._options.get(CONF_PROFILES, {})
            data: dict[str, Any] = {"profiles": {}}
            today = dt_util.utcnow().date()
            if self._last_reset != today:
                self._last_reset = today
                self._dli_totals = {}
            for pid, profile in profiles.items():
                metrics = await self._compute_metrics(pid, profile, now=dt_util.utcnow())
                data["profiles"][pid] = {
                    "name": profile.get("name"),
                    "metrics": metrics,
                }
            data["summary"] = self._summarise_profiles(data["profiles"])
            return data
        except Exception as err:  # pragma: no cover - simple stub
            raise UpdateFailed(str(err)) from err

    async def _compute_metrics(
        self,
        profile_id: str,
        profile: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute metrics for a profile.

        Currently only derives a rudimentary Daily Light Integral (DLI) based on the
        configured illuminance sensor. The conversion factor is not intended to be
        scientifically accurate but provides deterministic behaviour for testing.
        """

        now = now or dt_util.utcnow()
        sensors: dict[str, Any] = profile.get("sensors", {})
        illuminance = sensors.get("illuminance")
        temperature = sensors.get("temperature")
        humidity = sensors.get("humidity")
        moisture = sensors.get("moisture")
        dli: float | None = None
        ppfd: float | None = None
        vpd: float | None = None
        dew_point: float | None = None
        moisture_pct: float | None = None
        mold: float | None = None
        status: str | None = None

        if illuminance:
            state = self.hass.states.get(illuminance)
            if state is not None and state.state not in {"unknown", "unavailable"}:
                try:
                    lux = float(state.state)
                except (TypeError, ValueError):
                    lux = None
                if lux is not None:
                    ppfd = lux_to_ppfd(lux)
                    total = accumulate_dli(
                        self._dli_totals.get(profile_id, 0.0),
                        ppfd,
                        self.update_interval.total_seconds(),
                    )
                    self._dli_totals[profile_id] = total
                    dli = total

        t_c: float | None = None
        if temperature:
            t_state = self.hass.states.get(temperature)
            if t_state is not None and t_state.state not in {"unknown", "unavailable"}:
                try:
                    t = float(t_state.state)
                except (TypeError, ValueError):
                    t = None
                if t is not None:
                    unit = t_state.attributes.get("unit_of_measurement")
                    if unit == UnitOfTemperature.FAHRENHEIT:
                        t = TemperatureConverter.convert(t, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS)
                    t_c = t

        h: float | None = None
        if humidity:
            h_state = self.hass.states.get(humidity)
            if h_state is not None and h_state.state not in {"unknown", "unavailable"}:
                try:
                    h = float(h_state.state)
                except (TypeError, ValueError):
                    h = None

        if moisture:
            m_state = self.hass.states.get(moisture)
            if m_state is not None and m_state.state not in {"unknown", "unavailable"}:
                try:
                    moisture_pct = float(m_state.state)
                except (TypeError, ValueError):
                    moisture_pct = None

        if t_c is not None and h is not None:
            dew_point = dew_point_c(t_c, h)
            vpd = vpd_kpa(t_c, h)
            mold = mold_risk(t_c, h)

        status = profile_status(mold, moisture_pct)

        vpd_average = self._update_vpd_history(profile_id, vpd, now=now)

        return {
            "ppfd": ppfd,
            "dli": dli,
            "vpd": vpd,
            "vpd_7d_avg": vpd_average,
            "dew_point": dew_point,
            "moisture": moisture_pct,
            "mold_risk": mold,
            "status": status,
        }

    def _update_vpd_history(
        self,
        profile_id: str,
        vpd: float | None,
        *,
        now: datetime,
    ) -> float | None:
        """Track recent VPD samples to provide a rolling 7-day average."""

        history = self._vpd_history.setdefault(profile_id, deque())
        cutoff = now - timedelta(days=7)
        while history and history[0][0] < cutoff:
            history.popleft()
        if vpd is not None:
            with suppress(TypeError, ValueError):
                history.append((now, float(vpd)))
        if not history:
            return None
        return round(fmean(value for _ts, value in history), 3)

    def _summarise_profiles(self, profiles: dict[str, Any]) -> dict[str, Any]:
        """Build an aggregate summary across all monitored profiles."""

        if not profiles:
            return {
                "total_profiles": 0,
                "profiles_with_metrics": 0,
                "problem_profiles": 0,
                "ok_profiles": 0,
                "status_counts": {},
                "average_vpd": None,
                "average_vpd_7d": None,
                "average_moisture": None,
                "average_mold_risk": None,
                "average_dli": None,
                "last_updated": dt_util.utcnow().isoformat(),
            }

        statuses: list[str] = []
        vpd_values: list[float] = []
        vpd_trend_values: list[float] = []
        moisture_values: list[float] = []
        mold_values: list[float] = []
        dli_values: list[float] = []
        for payload in profiles.values():
            metrics = payload.get("metrics") or {}
            status = str(metrics.get("status") or "unknown")
            statuses.append(status)
            vpd_value = metrics.get("vpd")
            if isinstance(vpd_value, int | float):
                vpd_values.append(float(vpd_value))
            vpd_trend = metrics.get("vpd_7d_avg")
            if isinstance(vpd_trend, int | float):
                vpd_trend_values.append(float(vpd_trend))
            moisture_value = metrics.get("moisture")
            if isinstance(moisture_value, int | float):
                moisture_values.append(float(moisture_value))
            mold_value = metrics.get("mold_risk")
            if isinstance(mold_value, int | float):
                mold_values.append(float(mold_value))
            dli_value = metrics.get("dli")
            if isinstance(dli_value, int | float):
                dli_values.append(float(dli_value))

        counts = Counter(statuses)

        def _avg(values: list[float]) -> float | None:
            return round(fmean(values), 3) if values else None

        return {
            "total_profiles": len(profiles),
            "profiles_with_metrics": sum(1 for payload in profiles.values() if payload.get("metrics")),
            "status_counts": dict(counts),
            "problem_profiles": counts.get("warn", 0) + counts.get("critical", 0),
            "ok_profiles": counts.get("ok", 0),
            "average_vpd": _avg(vpd_values),
            "average_vpd_7d": _avg(vpd_trend_values),
            "average_moisture": _avg(moisture_values),
            "average_mold_risk": _avg(mold_values),
            "average_dli": _avg(dli_values),
            "last_updated": dt_util.utcnow().isoformat(),
        }
