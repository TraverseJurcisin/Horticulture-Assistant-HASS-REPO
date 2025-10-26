from __future__ import annotations

from collections.abc import Mapping
import contextlib
import importlib
import importlib.util
import logging
from types import SimpleNamespace
from typing import Any

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import services as ha_services
from .api import ChatApi
from .cloudsync import CloudSyncManager, CloudSyncPublisher
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PLANT_TYPE,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_KEEP_STALE,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    PROFILE_SCOPE_DEFAULT,
    PLATFORMS,
)
from .coordinator import HorticultureCoordinator
from .coordinator_ai import HortiAICoordinator
from .coordinator_local import HortiLocalCoordinator
from .entity_utils import ensure_entities_exist
from .health_monitor import async_release_dataset_health, async_setup_dataset_health
from .http import async_register_http_views
from .profile_registry import ProfileRegistry
from .profile_store import ProfileStore
from .profile.compat import sync_thresholds
from .profile.utils import ensure_sections
from .storage import LocalStore
from .utils.entry_helpers import (
    get_entry_plant_info,
    get_primary_profile_id,
    get_primary_profile_sensors,
    remove_entry_data,
    store_entry_data,
    update_entry_data,
)
from .utils.paths import ensure_local_data_paths

_CALIBRATION_SPEC = importlib.util.find_spec("custom_components.horticulture_assistant.calibration.services")
calibration_services = None
if _CALIBRATION_SPEC is not None:
    calibration_services = importlib.import_module("custom_components.horticulture_assistant.calibration.services")

__all__ = [
    "async_setup",
    "async_setup_entry",
    "async_migrate_entry",
    "async_unload_entry",
]

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(_hass: HomeAssistant, _config: dict) -> bool:
    """Set up the integration using YAML is not supported."""

    _LOGGER.debug("async_setup called: configuration entries only")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Horticulture Assistant from a ConfigEntry."""

    await ensure_local_data_paths(hass)
    await async_setup_dataset_health(hass)
    base_url = entry.options.get(CONF_BASE_URL, entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL))
    api_key = entry.options.get(CONF_API_KEY, entry.data.get(CONF_API_KEY, ""))
    model = entry.options.get(CONF_MODEL, entry.data.get(CONF_MODEL, DEFAULT_MODEL))
    keep_stale = entry.options.get(CONF_KEEP_STALE, entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE))
    update_minutes = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
    )

    api = ChatApi(hass, api_key, base_url, model)

    local_store = LocalStore(hass)
    await local_store.load()

    profile_store = ProfileStore(hass)
    await profile_store.async_init()

    cloud_sync_manager = CloudSyncManager(hass, entry)

    profile_registry = ProfileRegistry(hass, entry)
    await profile_registry.async_initialize()
    cloud_publisher = CloudSyncPublisher(cloud_sync_manager, entry.entry_id)
    profile_registry.attach_cloud_publisher(cloud_publisher)

    coordinator = HorticultureCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    ai_coordinator = HortiAICoordinator(
        hass,
        api,
        local_store,
        update_minutes,
        (local_store.data or {}).get("recommendation") if local_store.data else None,
    )
    local_coordinator = HortiLocalCoordinator(
        hass,
        local_store,
        update_minutes,
    )

    entry_data = store_entry_data(hass, entry)
    entry_data["dataset_monitor_attached"] = True
    entry_data.update(
        {
            "api": api,
            "profile_store": profile_store,
            "profile_registry": profile_registry,
            "profiles": profile_registry,
            "registry": profile_registry,
            "local_store": local_store,
            "coordinator": coordinator,
            "coordinator_ai": ai_coordinator,
            "coordinator_local": local_coordinator,
            "keep_stale": keep_stale,
            "cloud_sync_manager": cloud_sync_manager,
            "cloud_sync_status": cloud_sync_manager.status(),
            "cloud_publisher": cloud_publisher,
        }
    )

    async_register_http_views(hass)

    await cloud_sync_manager.async_start()
    entry_data["cloud_sync_status"] = cloud_sync_manager.status()

    domain_data = hass.data.setdefault(DOMAIN, {})
    domain_data["registry"] = profile_registry

    def _ensure_profile_entities(config_entry: ConfigEntry) -> None:
        primary_sensors = get_primary_profile_sensors(config_entry)
        if primary_sensors:
            sensor_ids = [value for value in primary_sensors.values() if isinstance(value, str)]
            if sensor_ids:
                ensure_entities_exist(
                    hass,
                    config_entry.data.get(CONF_PLANT_ID, config_entry.entry_id),
                    sensor_ids,
                )

        profile_options = config_entry.options.get(CONF_PROFILES, {})
        if isinstance(profile_options, dict):
            for profile_id, profile_data in profile_options.items():
                sensor_map = {}
                if isinstance(profile_data, dict):
                    raw = profile_data.get("sensors", {})
                    if isinstance(raw, dict):
                        sensor_map = raw
                if not sensor_map:
                    continue
                profile_sensors = [value for value in sensor_map.values() if isinstance(value, str)]
                if not profile_sensors:
                    continue
                ensure_entities_exist(
                    hass,
                    profile_id,
                    profile_sensors,
                    placeholders={
                        "plant_id": profile_id,
                        "profile_name": profile_data.get("name", profile_id)
                        if isinstance(profile_data, dict)
                        else profile_id,
                    },
                )

    _ensure_profile_entities(entry)

    await ha_services.async_register_all(
        hass,
        entry,
        ai_coordinator,
        local_coordinator,
        coordinator,
        profile_registry,
        local_store,
        cloud_manager=cloud_sync_manager,
    )
    ha_services.async_setup_services(hass)
    if calibration_services is not None:
        calibration_services.async_setup_services(hass)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    async def _async_entry_updated(hass: HomeAssistant, updated_entry: ConfigEntry) -> None:
        refreshed = update_entry_data(hass, updated_entry)
        refreshed["keep_stale"] = updated_entry.options.get(
            CONF_KEEP_STALE,
            updated_entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
        )
        coordinator.update_from_entry(updated_entry)
        refreshed["cloud_sync_status"] = cloud_sync_manager.status()
        _ensure_profile_entities(updated_entry)

    unsubscribe = entry.add_update_listener(hass, _async_entry_updated)
    entry.async_on_unload(unsubscribe)
    entry_data["update_listener_unsub"] = unsubscribe

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a ConfigEntry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data.get(DOMAIN, {})
        info = data.pop(entry.entry_id, None)
        if info:
            if info.get("dataset_monitor_attached"):
                await async_release_dataset_health(hass)
            manager = info.get("cloud_sync_manager")
            if manager and hasattr(manager, "async_stop"):
                with contextlib.suppress(Exception):
                    await manager.async_stop()
            profiles = info.get("profiles")
            if profiles and hasattr(profiles, "async_unload"):
                with contextlib.suppress(Exception):
                    await profiles.async_unload()
        remove_entry_data(hass, entry.entry_id)
    return unload_ok


def _coerce_dict(value: Any) -> dict[str, Any]:
    """Return ``value`` coerced into a mutable dictionary."""

    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _coerce_sensor_map(value: Any) -> dict[str, str]:
    """Return a mapping of sensor roles to entity ids."""

    sensors: dict[str, str] = {}
    for key, item in _coerce_dict(value).items():
        if isinstance(item, str) and item:
            sensors[str(key)] = item
    return sensors


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to the latest version."""

    data: dict[str, Any] = dict(entry.data)
    options: dict[str, Any] = dict(entry.options)
    migrated = False

    if entry.version < 2:
        migrated = True
        entry.version = 2
        if CONF_UPDATE_INTERVAL in data:
            options.setdefault(CONF_UPDATE_INTERVAL, data.pop(CONF_UPDATE_INTERVAL))
        options.setdefault(CONF_KEEP_STALE, data.pop(CONF_KEEP_STALE, DEFAULT_KEEP_STALE))

    if entry.version < 3:
        migrated = True
        entry.version = 3

        temp_entry = SimpleNamespace(
            data=data,
            options=options,
            entry_id=getattr(entry, "entry_id", DOMAIN),
        )
        derived_id, derived_name = get_entry_plant_info(temp_entry)
        plant_id = get_primary_profile_id(temp_entry) or derived_id or getattr(entry, "entry_id", DOMAIN)
        if not plant_id:
            plant_id = getattr(entry, "entry_id", DOMAIN)
        plant_name = derived_name or data.get(CONF_PLANT_NAME) or entry.title or plant_id

        raw_profiles = options.get(CONF_PROFILES)
        profiles: dict[str, dict[str, Any]] = {}
        if isinstance(raw_profiles, Mapping):
            for pid, payload in raw_profiles.items():
                if not isinstance(pid, str) or not pid:
                    continue
                profiles[pid] = _coerce_dict(payload)

        sensors_map = _coerce_sensor_map(options.get("sensors"))
        if not sensors_map:
            general_section = options.get("general")
            if isinstance(general_section, Mapping):
                sensors_map = _coerce_sensor_map(general_section.get("sensors"))

        thresholds_map = _coerce_dict(options.get("thresholds"))
        resolved_map = _coerce_dict(options.get("resolved_targets"))
        variables_map = _coerce_dict(options.get("variables"))
        sources_map = _coerce_dict(options.get("sources"))
        citations_map = _coerce_dict(options.get("citations"))

        base_profile = _coerce_dict(profiles.get(plant_id))
        display_name = base_profile.get("name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = plant_name
        base_profile["name"] = display_name
        base_profile.setdefault("display_name", display_name)
        base_profile["plant_id"] = plant_id
        base_profile["profile_id"] = plant_id

        existing_sensors = _coerce_sensor_map(base_profile.get("sensors"))
        existing_sensors.update(sensors_map)
        if existing_sensors:
            base_profile["sensors"] = existing_sensors

        plant_type = data.get(CONF_PLANT_TYPE)
        general_map = _coerce_dict(base_profile.get("general"))
        general_sensors = _coerce_sensor_map(general_map.get("sensors"))
        general_sensors.update(existing_sensors)
        if general_sensors:
            general_map["sensors"] = general_sensors
        if isinstance(plant_type, str) and plant_type:
            general_map.setdefault("plant_type", plant_type)
        scope_value = general_map.get(CONF_PROFILE_SCOPE) or base_profile.get(CONF_PROFILE_SCOPE)
        if not scope_value:
            scope_value = PROFILE_SCOPE_DEFAULT
        general_map[CONF_PROFILE_SCOPE] = scope_value
        base_profile["general"] = general_map

        thresholds_payload = {
            "thresholds": _coerce_dict(base_profile.get("thresholds")),
            "resolved_targets": _coerce_dict(base_profile.get("resolved_targets")),
            "variables": _coerce_dict(base_profile.get("variables")),
        }
        if thresholds_map:
            thresholds_payload["thresholds"].update(thresholds_map)
        if resolved_map:
            thresholds_payload["resolved_targets"].update(resolved_map)
        if variables_map:
            thresholds_payload["variables"].update(variables_map)
        if thresholds_payload["thresholds"] and (
            not thresholds_payload["resolved_targets"] or not thresholds_payload["variables"]
        ):
            sync_thresholds(thresholds_payload, default_source="imported")
        if thresholds_payload["thresholds"]:
            base_profile["thresholds"] = thresholds_payload["thresholds"]
        else:
            base_profile.pop("thresholds", None)
        if thresholds_payload["resolved_targets"]:
            base_profile["resolved_targets"] = thresholds_payload["resolved_targets"]
        else:
            base_profile.pop("resolved_targets", None)
        if thresholds_payload["variables"]:
            base_profile["variables"] = thresholds_payload["variables"]
        else:
            base_profile.pop("variables", None)

        existing_sources = _coerce_dict(base_profile.get("sources"))
        if sources_map:
            existing_sources.update(sources_map)
        if existing_sources:
            base_profile["sources"] = existing_sources

        existing_citations = _coerce_dict(base_profile.get("citations"))
        if citations_map:
            existing_citations.update(citations_map)
        if existing_citations:
            base_profile["citations"] = existing_citations

        for key in ("image_url", "species_display", "species_pid", "opb_credentials"):
            value = options.get(key)
            if value is not None and key not in base_profile:
                base_profile[key] = value

        profiles[plant_id] = base_profile

        normalised_profiles: dict[str, dict[str, Any]] = {}
        for pid, payload in profiles.items():
            prof = _coerce_dict(payload)
            prof.setdefault("plant_id", pid)
            prof.setdefault("profile_id", pid)
            name = prof.get("name") or prof.get("display_name") or pid
            if not isinstance(name, str):
                name = str(name)
            prof["name"] = name
            prof.setdefault("display_name", name)
            general = _coerce_dict(prof.get("general"))
            general_sensors = _coerce_sensor_map(general.get("sensors"))
            profile_sensors = _coerce_sensor_map(prof.get("sensors"))
            if profile_sensors:
                general_sensors.update(profile_sensors)
            if general_sensors:
                general["sensors"] = general_sensors
            if pid == plant_id and isinstance(plant_type, str) and plant_type:
                general.setdefault("plant_type", plant_type)
            if not general.get(CONF_PROFILE_SCOPE):
                general[CONF_PROFILE_SCOPE] = PROFILE_SCOPE_DEFAULT
            prof["general"] = general
            ensure_sections(prof, plant_id=pid, display_name=name)
            normalised_profiles[pid] = prof

        profiles = normalised_profiles
        options[CONF_PROFILES] = profiles

        primary_profile = profiles[plant_id]
        sensors_out = _coerce_sensor_map(primary_profile.get("sensors"))
        if sensors_out:
            options["sensors"] = sensors_out
        elif "sensors" in options:
            options.pop("sensors", None)

        for key in ("thresholds", "resolved_targets", "variables", "sources", "citations"):
            value = _coerce_dict(primary_profile.get(key))
            if value:
                options[key] = value
            else:
                options.pop(key, None)

        data.setdefault(CONF_PLANT_ID, plant_id)
        if isinstance(plant_name, str) and plant_name:
            data.setdefault(CONF_PLANT_NAME, plant_name)

    if migrated:
        hass.config_entries.async_update_entry(entry, data=data, options=options)

    return True
