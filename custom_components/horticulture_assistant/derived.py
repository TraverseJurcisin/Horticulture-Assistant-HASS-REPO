"""Derived environmental sensors for Horticulture Assistant."""
from __future__ import annotations

import math
from datetime import date

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN
from .entity_base import HorticultureBaseEntity


def _svp_kpa(t_c: float) -> float:
    """Return saturation vapor pressure in kPa."""
    return 0.6108 * math.exp((17.27 * t_c) / (t_c + 237.3))


def dew_point_c(t_c: float, rh: float) -> float:
    """Return dew point temperature in Celsius using Magnus formula."""
    a, b = 17.27, 237.3
    alpha = ((a * t_c) / (b + t_c)) + math.log(max(rh, 1e-6) / 100.0)
    return (b * alpha) / (a - alpha)


def _current_temp_humidity(
    hass: HomeAssistant, entry: ConfigEntry
) -> tuple[float | None, float | None]:
    """Return current temperature (°C) and humidity (%)."""
    sensors = entry.options.get("sensors", {})
    temp_id = sensors.get("temperature")
    hum_id = sensors.get("humidity")

    temp_state = hass.states.get(temp_id) if temp_id else None
    try:
        t = float(temp_state.state) if temp_state else None
    except (TypeError, ValueError):
        t = None
    if t is not None and temp_state:
        unit = temp_state.attributes.get("unit_of_measurement")
        if unit == UnitOfTemperature.FAHRENHEIT:
            t = TemperatureConverter.convert(
                t, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
            )

    hum_state = hass.states.get(hum_id) if hum_id else None
    try:
        h = float(hum_state.state) if hum_state else None
    except (TypeError, ValueError):
        h = None

    return t, h


class PlantDLISensor(HorticultureBaseEntity, SensorEntity):
    """Sensor calculating Daily Light Integral for a plant."""

    _attr_name = "Daily Light Integral"
    _attr_native_unit_of_measurement = "mol/m²/d"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        plant_name: str,
        plant_id: str,
    ) -> None:
        super().__init__(plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{plant_id}_dli"
        self._value: float | None = None
        self._accum: float = 0.0
        self._last_day: date | None = None
        self._last_ts = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        light_sensor = self._entry.options.get("sensors", {}).get("illuminance")
        if light_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [light_sensor], self._on_illuminance
                )
            )

    @callback
    def _on_illuminance(self, event) -> None:
        state = event.data.get("new_state")
        try:
            lx = float(state.state) if state else None
        except (TypeError, ValueError):
            lx = None
        if lx is None:
            return
        now = dt_util.utcnow()
        day = now.date()
        if self._last_day is None or day != self._last_day:
            self._accum = 0.0
            self._last_day = day
            self._last_ts = None
        coeff = self._entry.options.get("thresholds", {}).get("lux_to_ppfd", 0.0185)
        ppfd = lx * coeff
        if self._last_ts is None:
            seconds = 60
        else:
            seconds = (now - self._last_ts).total_seconds()
        self._accum += (ppfd * seconds) / 1_000_000
        self._value = round(self._accum, 2)
        self._last_ts = now
        self.async_write_ha_state()


class PlantVPDSensor(HorticultureBaseEntity, SensorEntity):
    """Sensor providing Vapor Pressure Deficit in kPa."""

    _attr_name = "Vapor Pressure Deficit"
    _attr_native_unit_of_measurement = "kPa"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, plant_name: str, plant_id: str) -> None:
        super().__init__(plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{plant_id}_vpd"
        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        sensors = self._entry.options.get("sensors", {})
        temp = sensors.get("temperature")
        hum = sensors.get("humidity")
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [e for e in (temp, hum) if e], self._on_state
            )
        )
        self.hass.loop.call_soon(self._on_state, None)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._entry)
        if t is None or h is None:
            self._value = None
        else:
            self._value = round(
                _svp_kpa(t) * (1 - max(min(h, 100.0), 0.0) / 100.0), 3
            )
        self.async_write_ha_state()


class PlantDewPointSensor(HorticultureBaseEntity, SensorEntity):
    """Sensor providing dew point temperature in Celsius."""

    _attr_name = "Dew Point"
    _attr_native_unit_of_measurement = "°C"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, plant_name: str, plant_id: str) -> None:
        super().__init__(plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{plant_id}_dew_point"
        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        sensors = self._entry.options.get("sensors", {})
        temp = sensors.get("temperature")
        hum = sensors.get("humidity")
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [e for e in (temp, hum) if e], self._on_state
            )
        )
        self.hass.loop.call_soon(self._on_state, None)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._entry)
        if t is None or h is None:
            self._value = None
        else:
            self._value = round(dew_point_c(t, h), 1)
        self.async_write_ha_state()


class PlantMoldRiskSensor(HorticultureBaseEntity, SensorEntity):
    """Sensor estimating mold growth risk on a 0..6 scale."""

    _attr_name = "Mold Risk"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, plant_name: str, plant_id: str) -> None:
        super().__init__(plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{plant_id}_mold_risk"
        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        sensors = self._entry.options.get("sensors", {})
        temp = sensors.get("temperature")
        hum = sensors.get("humidity")
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [e for e in (temp, hum) if e], self._on_state
            )
        )
        self.hass.loop.call_soon(self._on_state, None)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._entry)
        if t is None or h is None:
            self._value = None
        else:
            dp = dew_point_c(t, h)
            proximity = max(0.0, 1.0 - (t - dp) / 5.0)
            if h < 70:
                base = 0
            elif h < 80:
                base = 1
            elif h < 90:
                base = 3
            else:
                base = 5
            risk = min(6.0, base + proximity * 2.0)
            self._value = round(risk, 1)
        self.async_write_ha_state()
