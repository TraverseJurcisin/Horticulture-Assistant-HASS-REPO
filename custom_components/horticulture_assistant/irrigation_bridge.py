"""Simple adapters for irrigation providers."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN
from .entity_base import HorticultureBaseEntity


async def async_apply_irrigation(
    hass: HomeAssistant,
    provider: str,
    zone: str | None,
    seconds: float,
) -> None:
    """Apply an irrigation run time using the selected provider.

    provider -- either ``irrigation_unlimited`` or ``opensprinkler``.
    zone -- zone/station identifier required by the provider.
    seconds -- run time in seconds.
    """
    if provider == "irrigation_unlimited":
        await hass.services.async_call(
            "irrigation_unlimited",
            "run_zone",
            {"zone_id": zone, "time": float(seconds)},
            blocking=True,
        )
        return
    if provider == "opensprinkler":
        await hass.services.async_call(
            "opensprinkler",
            "run_once",
            {"station": zone, "duration": float(seconds)},
            blocking=True,
        )
        return
    raise ValueError(f"unknown provider {provider}")


class PlantIrrigationRecommendationSensor(HorticultureBaseEntity, SensorEntity):
    """Expose Smart Irrigation runtime recommendation."""

    _attr_name = "Recommended Irrigation"
    _attr_native_unit_of_measurement = "s"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, plant_name: str, plant_id: str) -> None:
        super().__init__(plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{plant_id}_irrigation_rec"
        self._src = entry.options.get("sensors", {}).get("smart_irrigation")
        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._src:
            self.async_on_remove(async_track_state_change_event(self.hass, [self._src], self._on_state))
            # prime value
            self._on_state(None)

    @callback
    def _on_state(self, _event) -> None:
        if not self._src:
            self._value = None
        else:
            state = self.hass.states.get(self._src)
            try:
                self._value = float(state.state) if state else None
            except (TypeError, ValueError):
                self._value = None
        self.async_write_ha_state()
