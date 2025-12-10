from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_CORE_CONFIG_UPDATE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CATEGORY_CONTROL, CONF_PROFILES, DOMAIN, signal_profile_contexts_updated
from .entity_base import HorticultureBaseEntity
from .profile.citations import manual_note
from .profile.compat import get_resolved_target, set_resolved_target
from .profile.schema import FieldAnnotation, ResolvedTarget
from .utils.entry_helpers import resolve_profile_context_collection

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
    collection = resolve_profile_context_collection(hass, entry)
    entity_registry = er.async_get(hass)
    domain_data = hass.data.setdefault(DOMAIN, {})
    add_lock: asyncio.Lock = domain_data.setdefault("add_entities_lock", asyncio.Lock())

    def _build_threshold_entities(context) -> list[ThresholdNumber]:
        profile_id = context.profile_id
        thresholds = context.thresholds
        name = context.name
        numbers: list[ThresholdNumber] = []
        for key, unit in THRESHOLD_SPECS:
            numbers.append(
                ThresholdNumber(
                    hass,
                    entry,
                    name,
                    profile_id,
                    key,
                    unit,
                    thresholds.get(key),
                )
            )
        return numbers

    known_profiles: set[str] = set()
    known_threshold_keys: dict[str, set[str]] = defaultdict(set)
    entities: list[ThresholdNumber] = []
    pending_specs: dict[str, set[str]] = {}

    def _sync_known_threshold_keys_from_registry() -> None:
        """Align tracked threshold specs with the entity registry."""

        registry_keys: dict[str, set[str]] = defaultdict(set)
        for entity_entry in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            if entity_entry.domain != "number" or entity_entry.platform != DOMAIN:
                continue
            unique_id = entity_entry.unique_id
            if not isinstance(unique_id, str):
                continue
            prefix = f"{entry.entry_id}_"
            if not unique_id.startswith(prefix) or "_" not in unique_id[len(prefix) :]:
                continue
            remainder = unique_id.removeprefix(prefix)
            profile_id, key = remainder.split("_", 1)
            registry_keys[profile_id].add(key)

        if registry_keys:
            known_threshold_keys.clear()
            for profile_id, keys in registry_keys.items():
                known_threshold_keys[profile_id].update(keys)
                known_profiles.add(profile_id)

    for context in collection.values():
        entities.extend(_build_threshold_entities(context))
        pending_specs[context.profile_id] = {key for key, _ in THRESHOLD_SPECS}

    async def _async_add_entities(new_entities: list[ThresholdNumber]) -> None:
        async with add_lock:
            add_result = async_add_entities(new_entities, update_before_add=True)
            if inspect.isawaitable(add_result):
                await add_result

    await _async_add_entities(entities)

    for profile_id, specs in pending_specs.items():
        known_profiles.add(profile_id)
        known_threshold_keys[profile_id].update(specs)

    _sync_known_threshold_keys_from_registry()

    @callback
    def _handle_profile_update(change: Mapping[str, Iterable[str]] | None) -> None:
        if not isinstance(change, Mapping):
            return
        added = tuple(change.get("added", ()))
        updated = tuple(change.get("updated", ()))
        removed = tuple(change.get("removed", ()))

        if removed:
            for profile_id in removed:
                known_profiles.discard(profile_id)
                known_threshold_keys.pop(profile_id, None)

        updated_collection = resolve_profile_context_collection(hass, entry)
        new_entities: list[ThresholdNumber] = []
        pending: dict[str, set[str]] = {}

        _sync_known_threshold_keys_from_registry()
        for profile_id in (*added, *updated):
            context = updated_collection.contexts.get(profile_id)
            if context is None:
                continue
            built_keys = known_threshold_keys.setdefault(profile_id, set())
            missing_specs = [(key, unit) for key, unit in THRESHOLD_SPECS if key not in built_keys]
            specs_to_build = missing_specs or (list(THRESHOLD_SPECS) if profile_id not in known_profiles else [])
            if not specs_to_build:
                continue
            for key, unit in specs_to_build:
                new_entities.append(
                    ThresholdNumber(
                        hass,
                        entry,
                        context.name,
                        profile_id,
                        key,
                        unit,
                        context.thresholds.get(key),
                    )
                )
                pending.setdefault(profile_id, set()).add(key)
            if profile_id not in known_profiles and profile_id not in pending:
                pending[profile_id] = set()

        for profile_id, specs in pending.items():
            known_profiles.add(profile_id)
            if specs:
                known_threshold_keys[profile_id].update(specs)

        def _reconcile_existing_contexts() -> list[ThresholdNumber]:
            reconciled: list[ThresholdNumber] = []
            pending_reconciled: dict[str, set[str]] = {}
            for profile_id, context in updated_collection.contexts.items():
                built_keys = known_threshold_keys.setdefault(profile_id, set())
                missing_specs = [(key, unit) for key, unit in THRESHOLD_SPECS if key not in built_keys]
                if not missing_specs:
                    known_profiles.add(profile_id)
                    continue
                for key, unit in missing_specs:
                    reconciled.append(
                        ThresholdNumber(
                            hass,
                            entry,
                            context.name,
                            profile_id,
                            key,
                            unit,
                            context.thresholds.get(key),
                        )
                    )
                    pending_reconciled.setdefault(profile_id, set()).add(key)
            for profile_id, specs in pending_reconciled.items():
                known_profiles.add(profile_id)
                known_threshold_keys[profile_id].update(specs)
            return reconciled

        new_entities.extend(_reconcile_existing_contexts())

        if new_entities:
            hass.async_create_task(_async_add_entities(new_entities))

    remove = async_dispatcher_connect(
        hass,
        signal_profile_contexts_updated(entry.entry_id),
        _handle_profile_update,
    )
    entry.async_on_unload(remove)


class ThresholdNumber(HorticultureBaseEntity, NumberEntity):
    """Configurable threshold number for a plant."""

    _attr_entity_category = CATEGORY_CONTROL
    _attr_mode = NumberMode.BOX
    _attr_native_step = 0.1

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
        super().__init__(entry.entry_id, plant_name, plant_id)
        self.hass = hass
        self._entry = entry
        self._key = key
        self._attr_name = key.replace("_", " ").title()
        self._attr_unique_id = self.profile_unique_id(key)
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
