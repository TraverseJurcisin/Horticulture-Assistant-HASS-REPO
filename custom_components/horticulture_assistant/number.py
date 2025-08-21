from __future__ import annotations

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CATEGORY_CONTROL
from .entity_base import HorticultureBaseEntity
from .utils.entry_helpers import get_entry_data, store_entry_data

THRESHOLD_SPECS = [
    ("temperature_min", UnitOfTemperature.CELSIUS),
    ("temperature_max", UnitOfTemperature.CELSIUS),
    ("humidity_min", "%"),
    ("humidity_max", "%"),
    ("illuminance_min", "lx"),
    ("illuminance_max", "lx"),
    ("moisture_min", "%"),
    ("moisture_max", "%"),
    ("conductivity_min", "µS/cm"),
    ("conductivity_max", "µS/cm"),
    ("vpd_min", "kPa"),
    ("vpd_max", "kPa"),
    ("lux_to_ppfd", "µmol/(m²·s·lx)"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    stored = get_entry_data(hass, entry) or store_entry_data(hass, entry)
    plant_id: str = stored["plant_id"]
    plant_name: str = stored["plant_name"]
    thresholds = entry.options.get("thresholds", {})

    entities: list[ThresholdNumber] = []
    for key, unit in THRESHOLD_SPECS:
        entities.append(
            ThresholdNumber(
                hass,
                entry,
                plant_name,
                plant_id,
                key,
                unit,
                thresholds.get(key),
            )
        )

    async_add_entities(entities)


class ThresholdNumber(HorticultureBaseEntity, NumberEntity):
    """Configurable threshold number for a plant."""

    _attr_entity_category = CATEGORY_CONTROL

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        plant_name: str,
        plant_id: str,
        key: str,
        unit: str,
        value: float | None,
    ) -> None:
        super().__init__(plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._key = key
        self._attr_name = key.replace("_", " ").title()
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{plant_id}_{key}"
        self._unit = unit
        self._attr_native_unit_of_measurement = None
        self._value = float(value) if value is not None else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        def _handle(event) -> None:
            self.hass.add_job(self.async_write_ha_state)

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _handle)
        )

    @property
    def native_value(self) -> float | None:
        if self._value is None:
            return None
        if self._key.startswith("temperature"):
            unit = self.hass.config.units.temperature_unit
            if unit == UnitOfTemperature.FAHRENHEIT:
                return self._value * 9 / 5 + 32
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        val = float(value)
        if self._key.startswith("temperature"):
            unit = self.hass.config.units.temperature_unit
            if unit == UnitOfTemperature.FAHRENHEIT:
                val = (val - 32) * 5 / 9
        self._value = val
        opts = dict(self._entry.options)
        thresholds = dict(opts.get("thresholds", {}))
        thresholds[self._key] = self._value
        opts["thresholds"] = thresholds
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()

    @property
    def native_unit_of_measurement(self):
        if self._key.startswith("temperature"):
            return self.hass.config.units.temperature_unit
        return self._unit
