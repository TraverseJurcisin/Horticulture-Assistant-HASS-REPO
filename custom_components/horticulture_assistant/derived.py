"""Derived environmental sensors for Horticulture Assistant."""

from __future__ import annotations

from datetime import date

import numpy as np
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

from .calibration.apply import lux_to_ppfd
from .calibration.fit import eval_model
from .calibration.store import async_get_for_entity
from .const import DOMAIN
from .engine.metrics import (
    accumulate_dli,
    dew_point_c,
    mold_risk,
    vpd_kpa,
)
from .engine.metrics import lux_to_ppfd as metric_lux_to_ppfd
from .entity_base import HorticultureBaseEntity


def _current_temp_humidity(hass: HomeAssistant, entry: ConfigEntry) -> tuple[float | None, float | None]:
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
            t = TemperatureConverter.convert(t, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS)

    hum_state = hass.states.get(hum_id) if hum_id else None
    try:
        h = float(hum_state.state) if hum_state else None
    except (TypeError, ValueError):
        h = None

    return t, h


class PlantDLISensor(HorticultureBaseEntity, SensorEntity):
    """Sensor calculating Daily Light Integral for a plant."""

    _attr_translation_key = "dli"
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
            self.async_on_remove(async_track_state_change_event(self.hass, [light_sensor], self._on_illuminance))

        self._light_sensor = light_sensor

    @callback
    def _on_illuminance(self, event) -> None:
        state = event.data.get("new_state")
        try:
            lx = float(state.state) if state else None
        except (TypeError, ValueError):
            lx = None
        if lx is None:
            return
        self.hass.async_create_task(self._process_lux(lx))

    async def _process_lux(self, lx: float) -> None:
        now = dt_util.now()
        day = now.date()
        if self._last_day is None or day != self._last_day:
            self._accum = 0.0
            self._last_day = day
            self._last_ts = None
        ppfd = await lux_to_ppfd(self.hass, self._light_sensor, lx)
        if ppfd is None:
            coeff = self._entry.options.get("thresholds", {}).get("lux_to_ppfd", 0.0185)
            ppfd = metric_lux_to_ppfd(lx, coeff)
        seconds = 60.0 if self._last_ts is None else max(0.0, (now - self._last_ts).total_seconds())
        self._accum = accumulate_dli(self._accum, ppfd, seconds)
        self._value = round(self._accum, 2)
        self._last_ts = now
        self.async_write_ha_state()


class PlantPPFDSensor(HorticultureBaseEntity, SensorEntity):
    """Sensor providing calibrated PPFD from Lux."""

    _attr_translation_key = "ppfd"
    _attr_native_unit_of_measurement = "µmol/m²/s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, plant_name: str, plant_id: str) -> None:
        super().__init__(plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{plant_id}_ppfd"
        self._value: float | None = None
        self._attrs: dict | None = None
        self._light_sensor: str | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    @property
    def extra_state_attributes(self):
        return self._attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._light_sensor = self._entry.options.get("sensors", {}).get("illuminance")
        if self._light_sensor:
            self.async_on_remove(async_track_state_change_event(self.hass, [self._light_sensor], self._on_lux))

    @callback
    def _on_lux(self, event) -> None:
        state = event.data.get("new_state")
        try:
            lx = float(state.state) if state else None
        except (TypeError, ValueError):
            lx = None
        if lx is None:
            return
        self.hass.async_create_task(self._update_ppfd(lx))

    async def _update_ppfd(self, lx: float) -> None:
        rec = await async_get_for_entity(self.hass, self._light_sensor) if self._light_sensor else None
        if rec:
            model = rec["model"]
            ppfd = float(eval_model(model["model"], model["coefficients"], np.array([lx]))[0])
            self._attrs = {
                "model": model["model"],
                "coefficients": model["coefficients"],
                "r2": model["r2"],
                "rmse": model["rmse"],
                "training_range_lux": [model["lux_min"], model["lux_max"]],
            }
            if lx < model["lux_min"] or lx > model["lux_max"]:
                self._attrs["extrapolating"] = True
        else:
            coeff = self._entry.options.get("thresholds", {}).get("lux_to_ppfd", 0.0185)
            ppfd = metric_lux_to_ppfd(lx, coeff)
            self._attrs = {"model": "constant", "coefficients": [coeff]}
        self._value = round(ppfd, 2)
        self.async_write_ha_state()


class PlantVPDSensor(HorticultureBaseEntity, SensorEntity):
    """Sensor providing Vapor Pressure Deficit in kPa."""

    _attr_translation_key = "vpd"
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
        self.async_on_remove(async_track_state_change_event(self.hass, [e for e in (temp, hum) if e], self._on_state))
        self.hass.loop.call_soon(self._on_state, None)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._entry)
        if t is None or h is None:
            self._value = None
        else:
            self._value = vpd_kpa(t, h)
        self.async_write_ha_state()


class PlantDewPointSensor(HorticultureBaseEntity, SensorEntity):
    """Sensor providing dew point temperature in Celsius."""

    _attr_translation_key = "dew_point"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
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
        self.async_on_remove(async_track_state_change_event(self.hass, [e for e in (temp, hum) if e], self._on_state))
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

    _attr_translation_key = "mold_risk"
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
        self.async_on_remove(async_track_state_change_event(self.hass, [e for e in (temp, hum) if e], self._on_state))
        self.hass.loop.call_soon(self._on_state, None)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._entry)
        if t is None or h is None:
            self._value = None
        else:
            self._value = mold_risk(t, h)
        self.async_write_ha_state()
