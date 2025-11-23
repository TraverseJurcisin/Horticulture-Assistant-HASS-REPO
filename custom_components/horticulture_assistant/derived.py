"""Derived environmental sensors for Horticulture Assistant."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

from .calibration.apply import lux_to_ppfd
from .calibration.store import async_get_for_entity
from .const import DOMAIN
from .engine.metrics import accumulate_dli, dew_point_c, lux_model_ppfd, mold_risk, vpd_kpa
from .engine.metrics import lux_to_ppfd as metric_lux_to_ppfd
from .entity_base import HorticultureBaseEntity, ProfileContextEntityMixin
from .utils.entry_helpers import ProfileContext


def _first_sensor(context: ProfileContext, key: str) -> str | None:
    """Return the first entity id for ``key`` from ``context``."""

    if not isinstance(context, ProfileContext):  # pragma: no cover - defensive
        return None
    return context.first_sensor(key)


def _current_temp_humidity(
    hass: HomeAssistant,
    context: ProfileContext,
) -> tuple[float | None, float | None]:
    """Return current temperature (°C) and humidity (%)."""

    temp_id = _first_sensor(context, "temperature")
    hum_id = _first_sensor(context, "humidity")

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


class PlantDLISensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Sensor calculating Daily Light Integral for a plant."""

    _attr_translation_key = "dli"
    _attr_native_unit_of_measurement = "mol/m²/d"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
    ) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(self, entry.entry_id, context.name, context.profile_id)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{context.profile_id}_dli"
        self._value: float | None = None
        self._accum: float = 0.0
        self._last_day: date | None = None
        self._last_ts = None
        self._thresholds = context.thresholds
        self._light_sensor: str | None = None
        self._light_unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        remove_cb = getattr(self, "async_on_remove", None)
        if callable(remove_cb):
            remove_cb(self._unsubscribe_light)
        self._subscribe_light_sensor(self._context)

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
            coeff = self._thresholds.get("lux_to_ppfd", 0.0185)
            ppfd = metric_lux_to_ppfd(lx, coeff)
        seconds = 60.0 if self._last_ts is None else max(0.0, (now - self._last_ts).total_seconds())
        self._accum = accumulate_dli(self._accum, ppfd, seconds)
        self._value = round(self._accum, 2)
        self._last_ts = now
        self.async_write_ha_state()

    def _unsubscribe_light(self) -> None:
        if self._light_unsub:
            self._light_unsub()
            self._light_unsub = None

    def _subscribe_light_sensor(self, context: ProfileContext | None) -> None:
        self._unsubscribe_light()
        if context is None:
            self._light_sensor = None
            self._thresholds = {}
            return
        self._thresholds = context.thresholds
        light_sensor = _first_sensor(context, "illuminance") or _first_sensor(context, "light")
        self._light_sensor = light_sensor
        if light_sensor:
            self._light_unsub = async_track_state_change_event(
                self.hass,
                [light_sensor],
                self._on_illuminance,
            )

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._subscribe_light_sensor(context)

    def _handle_context_removed(self) -> None:
        self._unsubscribe_light()
        self._thresholds = {}
        self._light_sensor = None
        self._value = None
        self._accum = 0.0
        self._last_day = None
        self._last_ts = None
        super()._handle_context_removed()


class PlantPPFDSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Sensor providing calibrated PPFD from Lux."""

    _attr_translation_key = "ppfd"
    _attr_native_unit_of_measurement = "µmol/m²/s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
    ) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(self, entry.entry_id, context.name, context.profile_id)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{context.profile_id}_ppfd"
        self._value: float | None = None
        self._attrs: dict | None = None
        self._light_sensor: str | None = None
        self._thresholds = context.thresholds
        self._light_unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    @property
    def extra_state_attributes(self):
        return self._attrs

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        remove_cb = getattr(self, "async_on_remove", None)
        if callable(remove_cb):
            remove_cb(self._unsubscribe_light)
        self._subscribe_light_sensor(self._context)

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
            ppfd = lux_model_ppfd(model["model"], model["coefficients"], lx)
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
            coeff = self._thresholds.get("lux_to_ppfd", 0.0185)
            ppfd = metric_lux_to_ppfd(lx, coeff)
            self._attrs = {"model": "constant", "coefficients": [coeff]}
        self._value = round(ppfd, 2)
        self.async_write_ha_state()

    def _unsubscribe_light(self) -> None:
        if self._light_unsub:
            self._light_unsub()
            self._light_unsub = None

    def _subscribe_light_sensor(self, context: ProfileContext | None) -> None:
        self._unsubscribe_light()
        if context is None:
            self._light_sensor = None
            self._thresholds = {}
            return
        self._thresholds = context.thresholds
        light_sensor = _first_sensor(context, "illuminance") or _first_sensor(context, "light")
        self._light_sensor = light_sensor
        if light_sensor:
            self._light_unsub = async_track_state_change_event(
                self.hass,
                [light_sensor],
                self._on_lux,
            )

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._subscribe_light_sensor(context)

    def _handle_context_removed(self) -> None:
        self._unsubscribe_light()
        self._thresholds = {}
        self._light_sensor = None
        self._value = None
        self._attrs = None
        super()._handle_context_removed()


class PlantVPDSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Sensor providing Vapor Pressure Deficit in kPa."""

    _attr_translation_key = "vpd"
    _attr_native_unit_of_measurement = "kPa"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
    ) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(self, entry.entry_id, context.name, context.profile_id)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{context.profile_id}_vpd"
        self._value: float | None = None
        self._state_unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        remove_cb = getattr(self, "async_on_remove", None)
        if callable(remove_cb):
            remove_cb(self._unsubscribe_state)
        self._subscribe_state_sensors(self._context)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._context) if self._context else (None, None)
        if t is None or h is None:
            self._value = None
        else:
            self._value = vpd_kpa(t, h)
        self.async_write_ha_state()

    def _unsubscribe_state(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None

    def _subscribe_state_sensors(self, context: ProfileContext | None) -> None:
        self._unsubscribe_state()
        if context is None:
            return
        temp = _first_sensor(context, "temperature")
        hum = _first_sensor(context, "humidity")
        entity_ids = [e for e in (temp, hum) if e]
        if entity_ids:
            self._state_unsub = async_track_state_change_event(
                self.hass,
                entity_ids,
                self._on_state,
            )
        loop = getattr(self.hass, "loop", None)
        if loop and hasattr(loop, "call_soon"):
            loop.call_soon(self._on_state, None)
        else:
            self._on_state(None)

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._subscribe_state_sensors(context)

    def _handle_context_removed(self) -> None:
        self._unsubscribe_state()
        self._value = None
        super()._handle_context_removed()


class PlantDewPointSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Sensor providing dew point temperature in Celsius."""

    _attr_translation_key = "dew_point"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
    ) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(self, entry.entry_id, context.name, context.profile_id)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{context.profile_id}_dew_point"
        self._value: float | None = None
        self._state_unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        remove_cb = getattr(self, "async_on_remove", None)
        if callable(remove_cb):
            remove_cb(self._unsubscribe_state)
        self._subscribe_state_sensors(self._context)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._context) if self._context else (None, None)
        if t is None or h is None:
            self._value = None
        else:
            self._value = round(dew_point_c(t, h), 1)
        self.async_write_ha_state()

    def _unsubscribe_state(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None

    def _subscribe_state_sensors(self, context: ProfileContext | None) -> None:
        self._unsubscribe_state()
        if context is None:
            return
        temp = _first_sensor(context, "temperature")
        hum = _first_sensor(context, "humidity")
        entity_ids = [e for e in (temp, hum) if e]
        if entity_ids:
            self._state_unsub = async_track_state_change_event(
                self.hass,
                entity_ids,
                self._on_state,
            )
        loop = getattr(self.hass, "loop", None)
        if loop and hasattr(loop, "call_soon"):
            loop.call_soon(self._on_state, None)
        else:
            self._on_state(None)

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._subscribe_state_sensors(context)

    def _handle_context_removed(self) -> None:
        self._unsubscribe_state()
        self._value = None
        super()._handle_context_removed()


class PlantMoldRiskSensor(ProfileContextEntityMixin, HorticultureBaseEntity, SensorEntity):
    """Sensor estimating mold growth risk on a 0..6 scale."""

    _attr_translation_key = "mold_risk"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        context: ProfileContext,
    ) -> None:
        ProfileContextEntityMixin.__init__(self, hass, entry, context)
        HorticultureBaseEntity.__init__(self, entry.entry_id, context.name, context.profile_id)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{context.profile_id}_mold_risk"
        self._value: float | None = None
        self._state_unsub: Callable[[], None] | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        remove_cb = getattr(self, "async_on_remove", None)
        if callable(remove_cb):
            remove_cb(self._unsubscribe_state)
        self._subscribe_state_sensors(self._context)

    @callback
    def _on_state(self, _event) -> None:
        t, h = _current_temp_humidity(self.hass, self._context) if self._context else (None, None)
        if t is None or h is None:
            self._value = None
        else:
            self._value = mold_risk(t, h)
        self.async_write_ha_state()

    def _unsubscribe_state(self) -> None:
        if self._state_unsub:
            self._state_unsub()
            self._state_unsub = None

    def _subscribe_state_sensors(self, context: ProfileContext | None) -> None:
        self._unsubscribe_state()
        if context is None:
            return
        temp = _first_sensor(context, "temperature")
        hum = _first_sensor(context, "humidity")
        entity_ids = [e for e in (temp, hum) if e]
        if entity_ids:
            self._state_unsub = async_track_state_change_event(
                self.hass,
                entity_ids,
                self._on_state,
            )
        loop = getattr(self.hass, "loop", None)
        if loop and hasattr(loop, "call_soon"):
            loop.call_soon(self._on_state, None)
        else:
            self._on_state(None)

    def _handle_context_updated(self, context: ProfileContext) -> None:
        super()._handle_context_updated(context)
        self._subscribe_state_sensors(context)

    def _handle_context_removed(self) -> None:
        self._unsubscribe_state()
        self._value = None
        super()._handle_context_removed()
