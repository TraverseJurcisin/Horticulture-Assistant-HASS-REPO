from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_CONTROL, CONF_PROFILES, DOMAIN
from .entity_base import HorticultureBaseEntity
from .profile.citations import manual_note
from .profile.compat import get_resolved_target, set_resolved_target
from .profile.schema import FieldAnnotation, ResolvedTarget
from .utils.entry_helpers import (
    get_entry_data,
    get_primary_profile_thresholds,
    store_entry_data,
)

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


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    stored = get_entry_data(hass, entry) or store_entry_data(hass, entry)
    plant_id: str = stored["plant_id"]
    plant_name: str = stored["plant_name"]
    thresholds = get_primary_profile_thresholds(entry)

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
        self._plant_id = plant_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        def _handle(event) -> None:
            self.hass.add_job(self.async_write_ha_state)

        self.async_on_remove(self.hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, _handle))

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

        citation = manual_note("Adjusted via number control")
        target = ResolvedTarget(
            value=self._value,
            annotation=FieldAnnotation(source_type="manual", method="manual"),
            citations=[citation],
        )

        set_resolved_target(opts, self._key, target)

        profiles = dict(opts.get(CONF_PROFILES, {}))
        if self._plant_id in profiles:
            prof = dict(profiles[self._plant_id])
            set_resolved_target(prof, self._key, target)
            citations_map = dict(prof.get("citations", {}))
            citations_map[self._key] = {
                "mode": citation.source,
                "ts": citation.accessed,
                "source_detail": (citation.details or {}).get("note"),
            }
            prof["citations"] = citations_map
            profiles[self._plant_id] = prof
            opts[CONF_PROFILES] = profiles

        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        self.async_write_ha_state()

    @property
    def native_unit_of_measurement(self):
        if self._key.startswith("temperature"):
            return self.hass.config.units.temperature_unit
        return self._unit

    def coordinator_entry_profile(self):
        profiles = self._entry.options.get(CONF_PROFILES, {})
        return profiles.get(self._plant_id, {})

    @property
    def extra_state_attributes(self):
        prof = self.coordinator_entry_profile()
        attrs: dict[str, Any] = {}

        target = get_resolved_target(prof, self._key)
        if target:
            extras = target.annotation.extras or {}
            detail = None
            if isinstance(extras, dict):
                detail = extras.get("summary") or extras.get("notes")
            if not detail and target.annotation.method:
                detail = target.annotation.method
            first = target.citations[0] if target.citations else None
            if not detail and first:
                if isinstance(first.details, dict):
                    detail = first.details.get("note") or first.details.get("summary")
                detail = detail or first.title
            attrs["source_mode"] = target.annotation.source_type
            attrs["source_detail"] = detail
            attrs["ai_confidence"] = target.annotation.confidence
            if first:
                attrs["last_resolved"] = first.accessed

        prov = (prof.get("citations", {}) or {}).get(self._key)
        src = (prof.get("sources", {}) or {}).get(self._key, {})
        attrs.setdefault("source_mode", src.get("mode"))
        attrs.setdefault("source_detail", (prov or {}).get("source_detail"))
        if attrs.get("ai_confidence") is None:
            attrs["ai_confidence"] = (src.get("ai") or {}).get("confidence")
        attrs.setdefault("last_resolved", (prov or {}).get("ts"))
        return attrs
