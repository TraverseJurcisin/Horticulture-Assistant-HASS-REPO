from __future__ import annotations

import inspect
import logging
from collections import Counter, deque
from collections.abc import Mapping, Sequence
from contextlib import suppress
from datetime import datetime, timedelta
from statistics import fmean
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.unit_conversion import TemperatureConverter

try:
    from homeassistant.util import dt as dt_util
except (ImportError, ModuleNotFoundError):  # pragma: no cover - tests without HA
    from datetime import date

    class _DtUtilModule:  # type: ignore[too-many-instance-attributes]
        date = date

    dt_util = _DtUtilModule()  # type: ignore[assignment]

try:
    from homeassistant.util.dt import utcnow
except (ImportError, ModuleNotFoundError):  # pragma: no cover - tests without HA
    from datetime import UTC, datetime

    def utcnow() -> datetime:
        return datetime.now(UTC)


from .const import CONF_PROFILES, CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES, DOMAIN
from .engine.metrics import accumulate_dli, dew_point_c, lux_to_ppfd, mold_risk, profile_status, vpd_kpa
from .utils.intervals import _normalise_update_minutes
from .utils.state_helpers import get_numeric_state, parse_entities

_LOGGER = logging.getLogger(__name__)


_FAHRENHEIT_UNITS = {
    "f",
    "°f",
    "ºf",
    "degf",
    "deg_f",
    "fahrenheit",
}


def _is_fahrenheit(unit: Any) -> bool:
    """Return ``True`` if ``unit`` represents degrees Fahrenheit."""

    if unit == UnitOfTemperature.FAHRENHEIT:
        return True
    if isinstance(unit, str):
        text = unit.strip().lower().replace("º", "°")
        text = text.replace(" ", "")
        return text in _FAHRENHEIT_UNITS
    return False


def _resolve_primary_entity_id(value: Any) -> str | None:
    """Return the primary entity id extracted from ``value``."""

    if value is None:
        return None

    if isinstance(value, Mapping):
        for key in ("entity_id", "entity", "id", "value"):
            candidate = value.get(key)
            if candidate is not None:
                resolved = _resolve_primary_entity_id(candidate)
                if resolved:
                    return resolved
        value = list(value.values())

    if isinstance(value, str | Sequence) and not isinstance(value, bytes | bytearray):
        entities = parse_entities(value)
    else:
        text = str(value).strip()
        if not text:
            return None
        entities = parse_entities([text])

    return entities[0] if entities else None


class HorticultureCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central data coordinator for plant profile metrics."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._entry: ConfigEntry = entry
        self._entry_id = entry.entry_id
        self._options: dict[str, Any] = dict(entry.options)
        self._dli_totals: dict[str, float] = {}
        self._vpd_history: dict[str, deque[tuple[datetime, float]]] = {}
        self._last_reset: dt_util.date | None = None

        interval = self._resolve_interval(entry)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{self._entry_id}",
            update_interval=timedelta(minutes=interval),
        )

    @staticmethod
    def _resolve_interval(entry: ConfigEntry) -> int:
        """Return the configured update interval in minutes."""

        options = getattr(entry, "options", {}) or {}
        data = getattr(entry, "data", {}) or {}
        candidate = (
            options.get(CONF_UPDATE_INTERVAL)
            or options.get("update_interval")
            or data.get(CONF_UPDATE_INTERVAL)
            or data.get("update_interval")
            or DEFAULT_UPDATE_MINUTES
        )
        return _normalise_update_minutes(candidate)

    def update_from_entry(self, entry: ConfigEntry) -> None:
        """Update coordinator options and polling interval from ``entry``."""

        self._entry = entry
        self._entry_id = entry.entry_id
        self._options = dict(entry.options)

        interval = self._resolve_interval(entry)
        new_interval = timedelta(minutes=interval)
        if self.update_interval != new_interval:
            self.update_interval = new_interval

    @property
    def entry_id(self) -> str:
        """Return the config entry id backing this coordinator."""

        return self._entry_id

    async def async_reset_dli(self, profile_id: str | None = None) -> None:
        """Reset accumulated DLI totals for a profile or all profiles."""

        if profile_id is None:
            self._dli_totals.clear()
        else:
            self._dli_totals.pop(profile_id, None)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            raw_profiles = self._options.get(CONF_PROFILES, {})
            if isinstance(raw_profiles, Mapping):
                profiles: dict[str, Any] = dict(raw_profiles)
            else:
                profiles = {}
            data: dict[str, Any] = {"profiles": {}}
            today = utcnow().date()
            if self._last_reset != today:
                self._last_reset = today
                self._dli_totals = {}
            for pid, profile in profiles.items():
                metrics = await self._compute_metrics(pid, profile, now=utcnow())
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

        now = now or utcnow()
        sensors: dict[str, Any] = profile.get("sensors", {})
        illuminance = _resolve_primary_entity_id(sensors.get("illuminance"))
        temperature = _resolve_primary_entity_id(sensors.get("temperature"))
        humidity = _resolve_primary_entity_id(sensors.get("humidity"))
        moisture = _resolve_primary_entity_id(sensors.get("moisture"))
        soil_temperature = _resolve_primary_entity_id(sensors.get("soil_temperature"))
        conductivity = _resolve_primary_entity_id(sensors.get("conductivity"))
        battery = _resolve_primary_entity_id(sensors.get("battery"))
        dli: float | None = None
        ppfd: float | None = None
        vpd: float | None = None
        dew_point: float | None = None
        moisture_pct: float | None = None
        mold: float | None = None
        status: str | None = None
        soil_temp_c: float | None = None
        conductivity_val: float | None = None
        battery_pct: float | None = None

        if illuminance:
            lux = get_numeric_state(self.hass, illuminance)
            if lux is not None:
                ppfd = lux_to_ppfd(lux)
                interval_td = self.update_interval
                interval_seconds = (
                    interval_td.total_seconds()
                    if interval_td is not None
                    else float(self._resolve_interval(self._entry) * 60)
                )
                total = accumulate_dli(
                    self._dli_totals.get(profile_id, 0.0),
                    ppfd,
                    interval_seconds,
                )
                self._dli_totals[profile_id] = total
                dli = total

        t_c: float | None = None
        if temperature:
            t = get_numeric_state(self.hass, temperature)
            if t is not None:
                t_state = self.hass.states.get(temperature)
                unit = t_state.attributes.get("unit_of_measurement") if t_state else None
                if _is_fahrenheit(unit):
                    t = TemperatureConverter.convert(t, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS)
                t_c = t

        h: float | None = None
        if humidity:
            h = get_numeric_state(self.hass, humidity)

        if moisture:
            moisture_pct = get_numeric_state(self.hass, moisture)

        if soil_temperature:
            soil_temp = get_numeric_state(self.hass, soil_temperature)
            if soil_temp is not None:
                soil_state = self.hass.states.get(soil_temperature)
                unit = soil_state.attributes.get("unit_of_measurement") if soil_state else None
                if _is_fahrenheit(unit):
                    soil_temp = TemperatureConverter.convert(
                        soil_temp,
                        UnitOfTemperature.FAHRENHEIT,
                        UnitOfTemperature.CELSIUS,
                    )
                soil_temp_c = soil_temp

        if conductivity:
            conductivity_val = get_numeric_state(self.hass, conductivity)

        if battery:
            battery_pct = get_numeric_state(self.hass, battery)

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
            "soil_temperature": soil_temp_c,
            "conductivity": conductivity_val,
            "battery": battery_pct,
        }

    async def async_shutdown(self) -> None:
        """Cancel scheduled refreshes and drop listeners."""

        if hasattr(self, "async_stop"):
            with suppress(Exception):
                await self.async_stop()

        debounced = getattr(self, "_debounced_refresh", None)
        if debounced is not None:
            with suppress(Exception):
                await debounced.async_cancel()

        unsub = getattr(self, "_unsub_refresh", None)
        if unsub is not None:
            with suppress(Exception):
                result = unsub()
                if inspect.isawaitable(result):
                    await result
            self._unsub_refresh = None

        listeners = getattr(self, "_listeners", None)
        if isinstance(listeners, dict):
            listeners.clear()

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
                "last_updated": utcnow().isoformat(),
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
            "last_updated": utcnow().isoformat(),
        }
