"""Service handlers for Horticulture Assistant.

These services expose high level operations for manipulating plant profiles
at runtime. They are intentionally lightweight wrappers around the
:class:`ProfileRegistry` to keep the integration's ``__init__`` module from
becoming monolithic.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.util
import inspect
import logging
import types
from collections.abc import Mapping
from enum import Enum, StrEnum
from typing import Any, Final

import homeassistant.core as ha_core
import voluptuous as vol

try:
    from homeassistant.components.sensor import SensorDeviceClass
except ModuleNotFoundError:  # pragma: no cover - fallback for unit tests without HA

    class SensorDeviceClass(StrEnum):
        """Minimal stand-in for Home Assistant's ``SensorDeviceClass``."""

        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"
        ILLUMINANCE = "illuminance"
        MOISTURE = "moisture"
        CO2 = "carbon_dioxide"
        PH = "ph"
        CONDUCTIVITY = "conductivity"


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .cloudsync.auth import CloudAuthClient, CloudAuthError, CloudAuthTokens
from .cloudsync.manager import CloudSyncError
from .const import (
    CONF_CLOUD_ACCESS_TOKEN,
    CONF_CLOUD_ACCOUNT_EMAIL,
    CONF_CLOUD_ACCOUNT_ROLES,
    CONF_CLOUD_AVAILABLE_ORGANIZATIONS,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_ORGANIZATION_ID,
    CONF_CLOUD_ORGANIZATION_NAME,
    CONF_CLOUD_ORGANIZATION_ROLE,
    CONF_CLOUD_REFRESH_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_TENANT_ID,
    CONF_CLOUD_TOKEN_EXPIRES_AT,
    CONF_PROFILES,
    DOMAIN,
    FEATURE_AI_ASSIST,
    FEATURE_IRRIGATION_AUTOMATION,
)
from .entitlements import FeatureUnavailableError, derive_entitlements
from .irrigation_bridge import async_apply_irrigation
from .profile.statistics import EVENT_STATS_VERSION, NUTRIENT_STATS_VERSION, SUCCESS_STATS_VERSION
from .profile_registry import ProfileRegistry
from .sensor import PlantProfileSensor
from .sensor_validation import collate_issue_messages, validate_sensor_links
from .storage import LocalStore
from .utils.entry_helpers import get_entry_data, get_primary_profile_id

try:
    _ER_SPEC = importlib.util.find_spec("homeassistant.helpers.entity_registry")
except (ModuleNotFoundError, ValueError):  # pragma: no cover - fallback for stub installs
    _ER_SPEC = None

if _ER_SPEC is not None:  # pragma: no branch - structure for clarity
    try:
        er = importlib.import_module("homeassistant.helpers.entity_registry")
    except (ModuleNotFoundError, ValueError):
        _ER_SPEC = None

if _ER_SPEC is None:  # pragma: no cover - fallback used in unit tests without Home Assistant

    class _EntityRegistryStub:
        def async_get_or_create(self, *args, **kwargs):
            return types.SimpleNamespace()

        def async_get_entity_id(self, *args, **kwargs):
            return None

        def async_get(self, entity_id):
            return None

    er = types.SimpleNamespace(async_get=lambda _hass: _EntityRegistryStub())

ServiceCall = getattr(ha_core, "ServiceCall", Any)
ServiceResponse = getattr(ha_core, "ServiceResponse", Any)

_LOGGER = logging.getLogger(__name__)
_MISSING: Final = object()
_REGISTERED = False

ENTITY_ID_SCHEMA = getattr(cv, "entity_id", vol.All(str, vol.Length(min=1)))

# Mapping of measurement names to expected device classes.  These roughly
# correspond to the roles supported by :mod:`update_sensors`.
MEASUREMENT_CLASSES: Final = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "soil_temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "illuminance": SensorDeviceClass.ILLUMINANCE,
    "moisture": SensorDeviceClass.MOISTURE,
    "co2": SensorDeviceClass.CO2,
    "ph": SensorDeviceClass.PH,
    "conductivity": SensorDeviceClass.CONDUCTIVITY,
    "battery": getattr(SensorDeviceClass, "BATTERY", "battery"),
}

SENSOR_TYPE_TO_MEASUREMENT: Final = {
    "air_temperature": "temperature",
    "air_humidity": "humidity",
    "soil_moisture": "moisture",
    "light": "illuminance",
    "soil_temperature": "soil_temperature",
    "battery_level": "battery",
    "soil_conductivity": "conductivity",
}

MEASUREMENT_TO_SENSOR_TYPE: Final = {value: key for key, value in SENSOR_TYPE_TO_MEASUREMENT.items()}

# Service name constants for profile management.
SERVICE_REPLACE_SENSOR = "replace_sensor"
SERVICE_LINK_SENSOR = "link_sensor"
SERVICE_REFRESH_SPECIES = "refresh_species"
SERVICE_CREATE_PROFILE = "create_profile"
SERVICE_DUPLICATE_PROFILE = "duplicate_profile"
SERVICE_DELETE_PROFILE = "delete_profile"
SERVICE_UPDATE_SENSORS = "update_sensors"
SERVICE_EXPORT_PROFILES = "export_profiles"
SERVICE_EXPORT_PROFILE = "export_profile"
SERVICE_IMPORT_PROFILES = "import_profiles"
SERVICE_IMPORT_TEMPLATE = "import_template"
SERVICE_REFRESH = "refresh"
SERVICE_RECOMPUTE = "recompute"
SERVICE_RESET_DLI = "reset_dli"
SERVICE_RECOMMEND_WATERING = "recommend_watering"
SERVICE_RECALCULATE_TARGETS = "recalculate_targets"
SERVICE_RUN_RECOMMENDATION = "run_recommendation"
SERVICE_APPLY_IRRIGATION_PLAN = "apply_irrigation_plan"
SERVICE_RESOLVE_PROFILE = "resolve_profile"
SERVICE_RESOLVE_ALL = "resolve_all"
SERVICE_GENERATE_PROFILE = "generate_profile"
SERVICE_CLEAR_CACHES = "clear_caches"
SERVICE_RECORD_RUN_EVENT = "record_run_event"
SERVICE_RECORD_HARVEST_EVENT = "record_harvest_event"
SERVICE_RECORD_NUTRIENT_EVENT = "record_nutrient_event"
SERVICE_RECORD_CULTIVATION_EVENT = "record_cultivation_event"
SERVICE_PROFILE_PROVENANCE = "profile_provenance"
SERVICE_PROFILE_RUNS = "profile_runs"
SERVICE_CLOUD_LOGIN = "cloud_login"
SERVICE_CLOUD_LOGOUT = "cloud_logout"
SERVICE_CLOUD_REFRESH = "cloud_refresh_token"
SERVICE_CLOUD_SELECT_ORG = "cloud_select_org"
SERVICE_CLOUD_SYNC_NOW = "cloud_sync_now"

SERVICE_NAMES: Final[tuple[str, ...]] = (
    SERVICE_REPLACE_SENSOR,
    SERVICE_LINK_SENSOR,
    SERVICE_REFRESH_SPECIES,
    SERVICE_CREATE_PROFILE,
    SERVICE_DUPLICATE_PROFILE,
    SERVICE_DELETE_PROFILE,
    SERVICE_UPDATE_SENSORS,
    SERVICE_EXPORT_PROFILES,
    SERVICE_EXPORT_PROFILE,
    SERVICE_IMPORT_PROFILES,
    SERVICE_IMPORT_TEMPLATE,
    SERVICE_REFRESH,
    SERVICE_RECOMPUTE,
    SERVICE_RESET_DLI,
    SERVICE_RECOMMEND_WATERING,
    SERVICE_RECALCULATE_TARGETS,
    SERVICE_RUN_RECOMMENDATION,
    SERVICE_APPLY_IRRIGATION_PLAN,
    SERVICE_RESOLVE_PROFILE,
    SERVICE_RESOLVE_ALL,
    SERVICE_GENERATE_PROFILE,
    SERVICE_CLEAR_CACHES,
    SERVICE_RECORD_RUN_EVENT,
    SERVICE_RECORD_HARVEST_EVENT,
    SERVICE_RECORD_NUTRIENT_EVENT,
    SERVICE_RECORD_CULTIVATION_EVENT,
    SERVICE_PROFILE_PROVENANCE,
    SERVICE_PROFILE_RUNS,
    SERVICE_CLOUD_LOGIN,
    SERVICE_CLOUD_LOGOUT,
    SERVICE_CLOUD_REFRESH,
    SERVICE_CLOUD_SELECT_ORG,
    SERVICE_CLOUD_SYNC_NOW,
)


async def async_register_all(
    hass: HomeAssistant,
    entry: ConfigEntry,
    ai_coord: DataUpdateCoordinator | None,
    local_coord: DataUpdateCoordinator | None,
    profile_coord: DataUpdateCoordinator | None,
    registry: ProfileRegistry,
    store: LocalStore,
    *,
    cloud_manager=None,
) -> None:
    """Register high level profile services."""

    global _REGISTERED
    if getattr(hass, "_horti_services_registered", False):
        return
    _REGISTERED = True
    hass._horti_services_registered = True

    entitlements = derive_entitlements(entry.options)

    def _update_entitlements(opts: Mapping[str, Any]) -> None:
        nonlocal entitlements
        entitlements = derive_entitlements(opts)

    register_service = hass.services.async_register

    def _register_service(
        service: str,
        handler,
        *,
        schema: vol.Schema | None = None,
        supports_response: bool = False,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if schema is not None:
            kwargs["schema"] = schema
        if supports_response:
            try:
                register_service(
                    DOMAIN,
                    service,
                    handler,
                    supports_response=True,
                    **kwargs,
                )
            except TypeError:
                register_service(DOMAIN, service, handler, **kwargs)
        else:
            register_service(DOMAIN, service, handler, **kwargs)

    async def _maybe_request_refresh(coordinator) -> None:
        refresh = getattr(coordinator, "async_request_refresh", None)
        if callable(refresh):
            await refresh()

    async_call = getattr(hass.services, "async_call", None)
    if async_call is not None:
        try:
            params = inspect.signature(async_call).parameters
        except (TypeError, ValueError):  # pragma: no cover - defensive
            params = {}
        if "return_response" not in params:

            async def _async_call(
                domain,
                service,
                data,
                *,
                blocking: bool = False,
                return_response: bool = False,
            ):
                func = hass.services.get((domain, service))
                if func is None:
                    return None
                result = func(types.SimpleNamespace(data=data))
                if asyncio.iscoroutine(result):
                    result = await result
                if blocking and hasattr(hass, "async_block_till_done"):
                    await hass.async_block_till_done()
                return result if return_response else None

            hass.services.async_call = _async_call

        def _require(feature: str) -> None:
            try:
                entitlements.ensure(feature)
            except FeatureUnavailableError as err:
                raise HomeAssistantError(str(err)) from err

    sensor_notification_id = f"horticulture_sensor_{entry.entry_id}"

    def _notify_sensor_warnings(issues) -> None:
        if not issues:
            return
        message = collate_issue_messages(issues)
        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Horticulture Assistant sensor warning",
                    "message": message,
                    "notification_id": sensor_notification_id,
                },
                blocking=False,
            )
        )

    def _clear_sensor_warning() -> None:
        if not hass.services.has_service("persistent_notification", "dismiss"):
            return

        hass.async_create_task(
            hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": sensor_notification_id},
                blocking=False,
            )
        )

    async def _async_update_runtime_sensor_link(profile_id: str, measurement: str, entity_id: str) -> None:
        sensor_type = MEASUREMENT_TO_SENSOR_TYPE.get(measurement)

        if sensor_type:
            raw_links = entry.options.get("linked_sensors")
            linked_options: dict[str, Any] = {}
            if isinstance(raw_links, Mapping):
                linked_options = dict(raw_links)
            linked_options[sensor_type] = entity_id
            new_options = {**entry.options, "linked_sensors": linked_options}
            hass.config_entries.async_update_entry(entry, options=new_options)
            entry.options = new_options

        if hass_data := hass.data.get(DOMAIN, {}):
            for entity in hass_data.get("entities", {}).values():
                if not isinstance(entity, PlantProfileSensor):
                    continue
                if entity.profile_id == profile_id and entity.sensor_type == sensor_type:
                    await entity.async_set_linked_sensor(entity_id)

    async def _refresh_profile() -> None:
        await _maybe_request_refresh(profile_coord)

    async def _apply_cloud_tokens(tokens: CloudAuthTokens, *, base_url: str) -> dict[str, Any]:
        """Persist refreshed cloud tokens via the cloud manager when available."""

        if cloud_manager is not None:
            opts = await cloud_manager.async_update_tokens(tokens, base_url=base_url)
        else:
            from .cloudsync.options import merge_cloud_tokens  # local import to avoid cycle

            opts = merge_cloud_tokens(entry.options, tokens, base_url=base_url)
            hass.config_entries.async_update_entry(entry, options=opts)
            entry.options = opts
            _update_entitlements(opts)
            registry.publish_full_snapshot()
        return opts

    async def _on_tokens_updated(opts: Mapping[str, Any]) -> None:
        _update_entitlements(opts)
        registry.publish_full_snapshot()

    if cloud_manager is not None:
        cloud_manager.register_token_listener(_on_tokens_updated)

    def _expected_device_class_name(device_class: SensorDeviceClass | str | None) -> str | None:
        if device_class is None:
            return None
        if isinstance(device_class, Enum):
            device_class = device_class.value
        return str(device_class).lower()

    def _normalise_registry_device_class(entry) -> str | None:
        value = getattr(entry, "device_class", None) or getattr(entry, "original_device_class", None)
        return _expected_device_class_name(value)

    async def _srv_replace_sensor(call) -> None:
        profile_id: str = call.data["profile_id"]
        measurement: str = call.data["measurement"]
        entity_id: str = call.data["entity_id"]

        if measurement not in MEASUREMENT_CLASSES:
            raise vol.Invalid(f"unknown measurement {measurement}")
        if hass.states.get(entity_id) is None:
            raise vol.Invalid(f"missing entity {entity_id}")

        reg = er.async_get(hass)
        reg_entry = reg.async_get(entity_id)
        expected = MEASUREMENT_CLASSES[measurement]
        validation = validate_sensor_links(hass, {measurement: entity_id})
        if validation.errors:
            raise vol.Invalid(collate_issue_messages(validation.errors))
        if validation.warnings:
            _notify_sensor_warnings(validation.warnings)
        else:
            _clear_sensor_warning()
        if reg_entry:
            actual = _normalise_registry_device_class(reg_entry)
            expected_name = _expected_device_class_name(expected)
            if expected_name and actual is not None and actual != expected_name:
                raise vol.Invalid("device class mismatch")
        try:
            await registry.async_replace_sensor(profile_id, measurement, entity_id)
        except ValueError as err:
            raise err
        await _async_update_runtime_sensor_link(profile_id, measurement, entity_id)
        await _maybe_request_refresh(profile_coord)
        await _refresh_profile()

    async def _srv_link_sensor(call) -> None:
        if "meter_entity" in call.data or "new_sensor" in call.data:
            meter_entity_id: str | None = call.data.get("meter_entity")
            new_sensor_id: str | None = call.data.get("new_sensor")

            if not meter_entity_id or not new_sensor_id:
                raise vol.Invalid("meter_entity and new_sensor are required")

            if hass.states.get(new_sensor_id) is None:
                raise vol.Invalid(f"missing entity {new_sensor_id}")

            reg = er.async_get(hass)
            ent_reg_entry = reg.async_get(meter_entity_id)
            if ent_reg_entry is None:
                raise vol.Invalid(f"entity {meter_entity_id} not found")

            new_sensor_registry_entry = reg.async_get(new_sensor_id)

            unique_id = ent_reg_entry.unique_id
            entity_obj = hass.data.get(DOMAIN, {}).get("entities", {}).get(unique_id)

            if entity_obj is None:
                raise vol.Invalid(f"entity object for {meter_entity_id} not available")

            expected_device_class = _expected_device_class_name(getattr(entity_obj, "device_class", None))
            actual_device_class = _normalise_registry_device_class(new_sensor_registry_entry)
            if expected_device_class and actual_device_class and expected_device_class != actual_device_class:
                raise vol.Invalid("device class mismatch")

            sensor_type = getattr(entity_obj, "sensor_type", None)
            if not sensor_type:
                raise vol.Invalid("plant profile sensor missing sensor_type")

            measurement = SENSOR_TYPE_TO_MEASUREMENT.get(sensor_type)
            if measurement:
                validation = validate_sensor_links(hass, {measurement: new_sensor_id})
                if validation.errors:
                    raise vol.Invalid(collate_issue_messages(validation.errors))
                if validation.warnings:
                    _notify_sensor_warnings(validation.warnings)
                else:
                    _clear_sensor_warning()

            target_entry_id = ent_reg_entry.config_entry_id or getattr(entity_obj, "_entry_id", None)
            target_entry = hass.config_entries.async_get_entry(target_entry_id)
            if target_entry is None:
                raise vol.Invalid("linked config entry missing")

            await entity_obj.async_set_linked_sensor(new_sensor_id)

            linked_options: dict[str, Any] = {}
            raw_links = target_entry.options.get("linked_sensors")
            if isinstance(raw_links, Mapping):
                linked_options = dict(raw_links)
            linked_options[sensor_type] = new_sensor_id

            new_options = {**target_entry.options, "linked_sensors": linked_options}
            hass.config_entries.async_update_entry(
                target_entry,
                options=new_options,
            )
            target_entry.options = new_options

            target_registry: ProfileRegistry | None = registry if target_entry.entry_id == entry.entry_id else None
            if target_registry is None:
                target_data = get_entry_data(hass, target_entry_id) or {}
                target_registry = target_data.get("profile_registry")

            if measurement and target_registry:
                profile_id = getattr(entity_obj, "profile_id", None) or get_primary_profile_id(target_entry)
                if profile_id:
                    try:
                        await target_registry.async_link_sensors(profile_id, {measurement: new_sensor_id})
                    except ValueError as err:
                        raise vol.Invalid(str(err)) from err

            _LOGGER.info("Linked %s to plant sensor %s", new_sensor_id, meter_entity_id)
            return

        profile_id: str = call.data["profile_id"]
        role: str = call.data["role"]
        entity_id: str = call.data["entity_id"]

        measurement = "moisture" if role == "soil_moisture" else role
        if measurement not in MEASUREMENT_CLASSES:
            raise vol.Invalid(f"unknown role {role}")
        if hass.states.get(entity_id) is None:
            raise vol.Invalid(f"missing entity {entity_id}")

        reg = er.async_get(hass)
        reg_entry = reg.async_get(entity_id)
        expected = MEASUREMENT_CLASSES[measurement]
        validation = validate_sensor_links(hass, {measurement: entity_id})
        if validation.errors:
            raise vol.Invalid(collate_issue_messages(validation.errors))
        if validation.warnings:
            _notify_sensor_warnings(validation.warnings)
        else:
            _clear_sensor_warning()
        if reg_entry:
            actual = _normalise_registry_device_class(reg_entry)
            expected_name = _expected_device_class_name(expected)
            if expected_name and actual is not None and actual != expected_name:
                raise vol.Invalid("device class mismatch")

        try:
            await registry.async_replace_sensor(profile_id, measurement, entity_id)
        except ValueError as err:
            raise err
        await _async_update_runtime_sensor_link(profile_id, measurement, entity_id)
        await _maybe_request_refresh(profile_coord)
        await _refresh_profile()

    async def _srv_refresh_species(call) -> None:
        profile_id: str = call.data["profile_id"]
        try:
            await registry.async_refresh_species(profile_id)
        except ValueError as err:
            raise err
        await _refresh_profile()

    async def _srv_export_profiles(call) -> None:
        path = call.data["path"]
        p = await registry.async_export(path)
        _LOGGER.info("Exported %d profiles to %s", len(registry), p)

    async def _srv_create_profile(call) -> None:
        name: str = call.data["name"]
        try:
            await registry.async_add_profile(name)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await _refresh_profile()

    async def _srv_duplicate_profile(call) -> None:
        src = call.data["source_profile_id"]
        new_name = call.data["new_name"]
        try:
            await registry.async_duplicate_profile(src, new_name)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await _refresh_profile()

    async def _srv_delete_profile(call) -> None:
        pid = call.data["profile_id"]
        try:
            await registry.async_delete_profile(pid)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await _refresh_profile()

    async def _srv_update_sensors(call) -> None:
        pid = call.data["profile_id"]
        sensors: dict[str, str] = {}
        for role in MEASUREMENT_CLASSES:
            entity_id = call.data.get(role)
            if isinstance(entity_id, str) and entity_id:
                sensors[role] = entity_id
        if sensors:
            validation = validate_sensor_links(hass, sensors)
            if validation.errors:
                raise HomeAssistantError(collate_issue_messages(validation.errors))
            if validation.warnings:
                _notify_sensor_warnings(validation.warnings)
            else:
                _clear_sensor_warning()
        else:
            _clear_sensor_warning()
        try:
            await registry.async_link_sensors(pid, sensors)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await _refresh_profile()

    async def _srv_export_profile(call) -> None:
        pid = call.data["profile_id"]
        path = call.data["path"]
        try:
            out = await registry.async_export_profile(pid, path)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        _LOGGER.info("Exported profile %s to %s", pid, out)

    async def _srv_record_run_event(call) -> ServiceResponse:
        profile_id: str = call.data["profile_id"]
        event_payload = {
            "run_id": call.data["run_id"],
            "started_at": call.data["started_at"],
        }
        if species_id := call.data.get("species_id"):
            event_payload["species_id"] = species_id
        if ended := call.data.get("ended_at"):
            event_payload["ended_at"] = ended
        if environment := call.data.get("environment"):
            event_payload["environment"] = dict(environment)
        if metadata := call.data.get("metadata"):
            event_payload["metadata"] = dict(metadata)
        for key in ("targets_met", "targets_total", "success_rate", "stress_events"):
            if key in call.data and call.data[key] is not None:
                event_payload[key] = call.data[key]

        try:
            stored = await registry.async_record_run_event(profile_id, event_payload)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        def _serialise_success(profile):
            if profile is None:
                return None
            for snapshot in getattr(profile, "computed_stats", []) or []:
                if snapshot.stats_version == SUCCESS_STATS_VERSION:
                    return snapshot.to_json()
            return None

        profile_obj = registry.get_profile(profile_id)
        profile_snapshot = _serialise_success(profile_obj)
        species_snapshot = None
        if profile_obj and getattr(profile_obj, "species", None):
            species_snapshot = _serialise_success(registry.get_profile(profile_obj.species))

        response: dict[str, Any] = {"run_event": stored.to_json()}
        success_payload: dict[str, Any] = {}
        if profile_snapshot is not None:
            success_payload["profile"] = profile_snapshot
        if species_snapshot is not None:
            success_payload["species"] = species_snapshot
        if success_payload:
            response["success_statistics"] = success_payload
        return response

    async def _srv_record_harvest_event(call) -> ServiceResponse:
        profile_id: str = call.data["profile_id"]
        event_payload = {
            "harvest_id": call.data["harvest_id"],
            "harvested_at": call.data["harvested_at"],
            "yield_grams": call.data["yield_grams"],
        }
        for key in ("species_id", "run_id"):
            if value := call.data.get(key):
                event_payload[key] = value
        for key in ("area_m2", "wet_weight_grams", "dry_weight_grams"):
            if key in call.data and call.data[key] is not None:
                event_payload[key] = call.data[key]
        if call.data.get("fruit_count") is not None:
            event_payload["fruit_count"] = call.data["fruit_count"]
        if metadata := call.data.get("metadata"):
            event_payload["metadata"] = dict(metadata)

        try:
            stored = await registry.async_record_harvest_event(profile_id, event_payload)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        profile = registry.get_profile(profile_id)
        statistics = [stat.to_json() for stat in profile.statistics] if profile else []
        return {
            "harvest_event": stored.to_json(),
            "statistics": statistics,
        }

    async def _srv_record_nutrient_event(call) -> ServiceResponse:
        profile_id: str = call.data["profile_id"]
        event_payload = {
            "event_id": call.data["event_id"],
            "applied_at": call.data["applied_at"],
        }
        for key in ("species_id", "run_id", "product_id", "product_name", "product_category", "source"):
            if value := call.data.get(key):
                event_payload[key] = value
        for key in ("solution_volume_liters", "concentration_ppm", "ec_ms", "ph"):
            if key in call.data and call.data[key] is not None:
                event_payload[key] = call.data[key]
        if additives := call.data.get("additives"):
            event_payload["additives"] = list(additives)
        if metadata := call.data.get("metadata"):
            event_payload["metadata"] = dict(metadata)

        try:
            stored = await registry.async_record_nutrient_event(profile_id, event_payload)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        def _snapshot(profile):
            if profile is None:
                return None
            for snapshot in getattr(profile, "computed_stats", []) or []:
                if snapshot.stats_version == NUTRIENT_STATS_VERSION:
                    return snapshot.to_json()
            return None

        profile_obj = registry.get_profile(profile_id)
        profile_snapshot = _snapshot(profile_obj)
        species_snapshot = None
        if profile_obj and getattr(profile_obj, "species", None):
            species_snapshot = _snapshot(registry.get_profile(profile_obj.species))

        response: dict[str, Any] = {"nutrient_event": stored.to_json()}
        if profile_snapshot or species_snapshot:
            payload: dict[str, Any] = {}
            if profile_snapshot:
                payload["profile"] = profile_snapshot
            if species_snapshot:
                payload["species"] = species_snapshot
            response["nutrient_statistics"] = payload

        return response

    async def _srv_record_cultivation_event(call) -> ServiceResponse:
        profile_id: str = call.data["profile_id"]
        event_payload: dict[str, Any] = {
            "event_id": call.data["event_id"],
            "occurred_at": call.data["occurred_at"],
            "event_type": call.data["event_type"],
        }
        for key in ("species_id", "run_id", "title", "notes", "metric_unit", "actor", "location"):
            if value := call.data.get(key):
                event_payload[key] = value
        if "metric_value" in call.data and call.data["metric_value"] is not None:
            event_payload["metric_value"] = call.data["metric_value"]
        if tags := call.data.get("tags"):
            event_payload["tags"] = list(tags)
        if metadata := call.data.get("metadata"):
            event_payload["metadata"] = dict(metadata)

        try:
            stored = await registry.async_record_cultivation_event(profile_id, event_payload)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

        def _snapshot(profile):
            if profile is None:
                return None
            for snapshot in getattr(profile, "computed_stats", []) or []:
                if snapshot.stats_version == EVENT_STATS_VERSION:
                    return snapshot.to_json()
            return None

        profile_obj = registry.get_profile(profile_id)
        profile_snapshot = _snapshot(profile_obj)
        species_snapshot = None
        if profile_obj and getattr(profile_obj, "species", None):
            species_snapshot = _snapshot(registry.get_profile(profile_obj.species))

        response: dict[str, Any] = {"cultivation_event": stored.to_json()}
        if profile_snapshot or species_snapshot:
            payload: dict[str, Any] = {}
            if profile_snapshot:
                payload["profile"] = profile_snapshot
            if species_snapshot:
                payload["species"] = species_snapshot
            response["event_statistics"] = payload

        return response

    async def _srv_profile_provenance(call) -> ServiceResponse:
        profile_id: str = call.data["profile_id"]
        include_overlay: bool = bool(call.data.get("include_overlay", False))
        include_extras: bool = bool(call.data.get("include_extras", False))
        include_citations: bool = bool(call.data.get("include_citations", False))

        profile = registry.get_profile(profile_id)
        if profile is None:
            raise HomeAssistantError(f"unknown profile {profile_id}")

        profile.refresh_sections()
        summary = profile.provenance_summary()
        detailed = profile.resolved_provenance(
            include_overlay=include_overlay,
            include_extras=include_extras,
            include_citations=include_citations,
        )

        inherited: list[str] = []
        overrides: list[str] = []
        external: list[str] = []
        computed: list[str] = []

        for key, meta in summary.items():
            source = str(meta.get("source_type"))
            if meta.get("is_inherited"):
                inherited.append(key)
            elif source in {"manual", "local_override"}:
                overrides.append(key)
            elif source == "computed":
                computed.append(key)
            else:
                external.append(key)

        badges = profile.provenance_badges()

        response: dict[str, Any] = {
            "profile_id": profile_id,
            "profile_name": profile.display_name,
            "summary": summary,
            "resolved_provenance": detailed,
            "groups": {
                "inherited": sorted(inherited),
                "overrides": sorted(overrides),
                "external": sorted(external),
                "computed": sorted(computed),
            },
            "counts": {
                "total": len(summary),
                "inherited": len(inherited),
                "overrides": len(overrides),
                "external": len(external),
                "computed": len(computed),
            },
        }
        if badges:
            response["badges"] = badges
            response["badge_counts"] = {
                "inherited": sum(1 for meta in badges.values() if meta.get("badge") == "inherited"),
                "override": sum(1 for meta in badges.values() if meta.get("badge") == "override"),
                "external": sum(1 for meta in badges.values() if meta.get("badge") == "external"),
                "computed": sum(1 for meta in badges.values() if meta.get("badge") == "computed"),
            }
        if profile.last_resolved:
            response["last_resolved"] = profile.last_resolved
        return response

    async def _srv_profile_runs(call) -> ServiceResponse:
        profile_id: str = call.data["profile_id"]
        profile = registry.get_profile(profile_id)
        if profile is None:
            raise HomeAssistantError(f"unknown profile {profile_id}")
        limit = call.data.get("limit")
        limit_value: int | None
        if limit is None:
            limit_value = None
        else:
            try:
                limit_value = max(1, int(limit))
            except (TypeError, ValueError):
                raise HomeAssistantError("limit must be an integer") from None
        runs = profile.run_summaries(limit=limit_value)
        return {"profile_id": profile_id, "runs": runs}

    async def _srv_cloud_login(call) -> ServiceResponse:
        base_url = str(call.data.get("base_url") or entry.options.get(CONF_CLOUD_BASE_URL, "")).strip()
        if not base_url:
            raise HomeAssistantError("base_url is required for cloud login")
        email = str(call.data.get("email") or "").strip()
        password = str(call.data.get("password") or "")
        if not email or not password:
            raise HomeAssistantError("email and password are required")

        session = async_get_clientsession(hass)
        client = CloudAuthClient(base_url, session=session)
        try:
            tokens = await client.async_login(email, password)
        except CloudAuthError as err:
            raise HomeAssistantError(str(err)) from err

        opts = await _apply_cloud_tokens(tokens, base_url=base_url)
        return {
            "tenant_id": tokens.tenant_id,
            "account_email": tokens.account_email,
            "token_expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
            "organization_id": opts.get(CONF_CLOUD_ORGANIZATION_ID),
            "organization_name": opts.get(CONF_CLOUD_ORGANIZATION_NAME),
        }

    async def _srv_cloud_logout(call) -> ServiceResponse:
        opts = dict(entry.options)
        opts[CONF_CLOUD_SYNC_ENABLED] = False
        for key in (
            CONF_CLOUD_ACCESS_TOKEN,
            CONF_CLOUD_REFRESH_TOKEN,
            CONF_CLOUD_TOKEN_EXPIRES_AT,
            CONF_CLOUD_ACCOUNT_EMAIL,
            CONF_CLOUD_ACCOUNT_ROLES,
            CONF_CLOUD_DEVICE_TOKEN,
            CONF_CLOUD_AVAILABLE_ORGANIZATIONS,
            CONF_CLOUD_ORGANIZATION_ID,
            CONF_CLOUD_ORGANIZATION_NAME,
            CONF_CLOUD_ORGANIZATION_ROLE,
        ):
            opts.pop(key, None)
        hass.config_entries.async_update_entry(entry, options=opts)
        entry.options = opts
        _update_entitlements(opts)
        if cloud_manager is not None:
            await cloud_manager.async_refresh()
        registry.publish_full_snapshot()
        return {"status": "logged_out"}

    async def _srv_cloud_refresh(call) -> ServiceResponse:
        base_url = str(call.data.get("base_url") or entry.options.get(CONF_CLOUD_BASE_URL, "")).strip()
        if not base_url:
            raise HomeAssistantError("base_url is required for token refresh")

        if cloud_manager is not None:
            try:
                opts = await cloud_manager.async_trigger_token_refresh(force=True, base_url=base_url)
            except CloudAuthError as err:
                raise HomeAssistantError(str(err)) from err
            if not opts:
                raise HomeAssistantError("token refresh did not update credentials")
            expiry = opts.get(CONF_CLOUD_TOKEN_EXPIRES_AT) or entry.options.get(CONF_CLOUD_TOKEN_EXPIRES_AT)
            return {
                "token_expires_at": expiry,
                "tenant_id": opts.get(CONF_CLOUD_TENANT_ID),
                "organization_id": opts.get(CONF_CLOUD_ORGANIZATION_ID),
                "organization_name": opts.get(CONF_CLOUD_ORGANIZATION_NAME),
            }

        refresh_token = entry.options.get(CONF_CLOUD_REFRESH_TOKEN)
        if not refresh_token:
            raise HomeAssistantError("no refresh token available")

        session = async_get_clientsession(hass)
        client = CloudAuthClient(base_url, session=session)
        try:
            tokens = await client.async_refresh(refresh_token)
        except CloudAuthError as err:
            raise HomeAssistantError(str(err)) from err

        opts = await _apply_cloud_tokens(tokens, base_url=base_url)
        return {
            "token_expires_at": tokens.expires_at.isoformat() if tokens.expires_at else None,
            "tenant_id": opts.get(CONF_CLOUD_TENANT_ID),
            "organization_id": opts.get(CONF_CLOUD_ORGANIZATION_ID),
            "organization_name": opts.get(CONF_CLOUD_ORGANIZATION_NAME),
        }

    async def _srv_cloud_select_org(call) -> ServiceResponse:
        available = entry.options.get(CONF_CLOUD_AVAILABLE_ORGANIZATIONS) or []
        if not isinstance(available, list) or not available:
            raise HomeAssistantError("no cloud organizations available to select")

        requested_id = str(call.data.get("organization_id") or "").strip()
        requested_name = str(call.data.get("organization_name") or "").strip()
        requested_role = str(call.data.get("role") or "").strip()
        if not requested_id and not requested_name:
            raise HomeAssistantError("organization_id or organization_name must be provided")

        match: Mapping[str, Any] | None = None
        for org in available:
            if not isinstance(org, Mapping):
                continue
            candidate_id = str(org.get("id") or org.get("org_id") or "").strip()
            candidate_name = str(org.get("name") or org.get("label") or "").strip()
            if requested_id and candidate_id and candidate_id.lower() == requested_id.lower():
                match = org
                break
            if requested_name and candidate_name and candidate_name.lower() == requested_name.lower():
                match = org
                break
        if match is None:
            raise HomeAssistantError("requested organization not found")

        selected_id = str(match.get("id") or match.get("org_id") or "").strip()
        selected_name = str(match.get("name") or match.get("label") or selected_id).strip()
        roles_raw = match.get("roles")
        if isinstance(roles_raw, str) and roles_raw:
            derived_role = roles_raw
        elif isinstance(roles_raw, list | tuple) and roles_raw:
            derived_role = str(roles_raw[0])
        else:
            derived_role = ""
        if requested_role:
            derived_role = requested_role

        opts = dict(entry.options)
        opts[CONF_CLOUD_ORGANIZATION_ID] = selected_id
        opts[CONF_CLOUD_ORGANIZATION_NAME] = selected_name or selected_id
        if derived_role:
            opts[CONF_CLOUD_ORGANIZATION_ROLE] = derived_role
        else:
            opts.pop(CONF_CLOUD_ORGANIZATION_ROLE, None)

        updated_orgs: list[dict[str, Any]] = []
        for org in available:
            if not isinstance(org, Mapping):
                continue
            org_copy = dict(org)
            org_copy_id = str(org_copy.get("id") or org_copy.get("org_id") or "").strip()
            org_copy["default"] = bool(org_copy_id and org_copy_id == selected_id)
            updated_orgs.append(org_copy)
        opts[CONF_CLOUD_AVAILABLE_ORGANIZATIONS] = updated_orgs

        hass.config_entries.async_update_entry(entry, options=opts)
        entry.options = opts
        _update_entitlements(opts)
        if cloud_manager is not None:
            await cloud_manager.async_refresh()
        registry.publish_full_snapshot()
        return {
            "organization_id": selected_id,
            "organization_name": selected_name,
            "organization_role": opts.get(CONF_CLOUD_ORGANIZATION_ROLE),
        }

    async def _srv_cloud_sync_now(call) -> ServiceResponse:
        if cloud_manager is None:
            raise HomeAssistantError("cloud sync is not configured for this entry")
        push_raw = call.data.get("push")
        pull_raw = call.data.get("pull")
        push = True if push_raw is None else bool(push_raw)
        pull = True if pull_raw is None else bool(pull_raw)
        try:
            result = await cloud_manager.async_sync_now(push=push, pull=pull)
        except CloudSyncError as err:
            raise HomeAssistantError(str(err)) from err
        return result

    async def _srv_import_profiles(call) -> None:
        path = call.data["path"]
        await registry.async_import_profiles(path)
        await _refresh_profile()

    async def _srv_import_template(call) -> None:
        template = call.data["template"]
        name = call.data.get("name")
        try:
            await registry.async_import_template(template, name)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await _refresh_profile()

    async def _srv_refresh(call) -> None:
        await _maybe_request_refresh(ai_coord)
        await _maybe_request_refresh(local_coord)
        await _maybe_request_refresh(profile_coord)

    async def _srv_recompute(call) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_id:
            profiles = entry.options.get(CONF_PROFILES, {})
            if profile_id not in profiles:
                raise HomeAssistantError(f"unknown profile {profile_id}")
        await _maybe_request_refresh(profile_coord)

    async def _srv_reset_dli(call: ServiceCall) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_coord:
            await profile_coord.async_reset_dli(profile_id)

    async def _srv_recommend_watering(call: ServiceCall) -> ServiceResponse:
        """Suggest a watering duration based on profile metrics."""

        pid: str = call.data["profile_id"]
        _require(FEATURE_IRRIGATION_AUTOMATION)
        if profile_coord is None:
            raise HomeAssistantError("profile coordinator unavailable")
        metrics = profile_coord.data.get("profiles", {}).get(pid, {}).get("metrics") if profile_coord.data else None
        if metrics is None:
            raise HomeAssistantError(f"unknown profile {pid}")
        moisture = metrics.get("moisture")
        dli = metrics.get("dli")
        minutes = 0
        if moisture is not None:
            if moisture < 20:
                minutes += 10
            elif moisture < 30:
                minutes += 5
        if dli is not None and dli < 8:
            minutes += 5
        return {"minutes": minutes}

    async def _srv_recalculate_targets(call) -> None:
        plant_id = call.data["plant_id"]
        assert store.data is not None
        plants = store.data.setdefault("plants", {})
        if plant_id not in plants:
            raise HomeAssistantError(f"unknown plant {plant_id}")
        await _maybe_request_refresh(local_coord)

    async def _srv_run_recommendation(call) -> None:
        plant_id = call.data["plant_id"]
        _require(FEATURE_AI_ASSIST)
        assert store.data is not None
        plants = store.data.setdefault("plants", {})
        if plant_id not in plants:
            raise HomeAssistantError(f"unknown plant {plant_id}")
        prev = _MISSING
        if ai_coord and isinstance(ai_coord.data, Mapping):
            prev = ai_coord.data.get("recommendation", _MISSING)
        if ai_coord:
            with contextlib.suppress(UpdateFailed):
                await _maybe_request_refresh(ai_coord)
        if call.data.get("approve") and ai_coord:
            plant = plants.setdefault(plant_id, {})
            data = ai_coord.data if isinstance(ai_coord.data, Mapping) else None
            recommendation = _MISSING
            if data and "recommendation" in data:
                recommendation = data["recommendation"]
            elif prev is not _MISSING:
                recommendation = prev
            elif "recommendation" in plant:
                recommendation = plant["recommendation"]

            if recommendation is _MISSING:
                recommendation = None

            plant["recommendation"] = recommendation
            await store.save()

    async def _srv_apply_irrigation(call) -> None:
        profile_id = call.data["profile_id"]
        _require(FEATURE_IRRIGATION_AUTOMATION)
        provider = call.data.get("provider", "auto")
        zone = call.data.get("zone")
        reg = er.async_get(hass)
        unique_id = f"{profile_id}_irrigation_rec"
        rec_entity = reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        seconds: float | None = None
        if rec_entity:
            state = hass.states.get(rec_entity)
            try:
                seconds = float(state.state)
            except (TypeError, ValueError):
                seconds = None
        if seconds is None:
            raise HomeAssistantError("no recommendation available")

        if provider == "auto":
            if hass.services.has_service("irrigation_unlimited", "run_zone"):
                provider = "irrigation_unlimited"
            elif hass.services.has_service("opensprinkler", "run_once"):
                provider = "opensprinkler"
            else:
                raise HomeAssistantError("no irrigation provider")

        await async_apply_irrigation(hass, provider, zone, seconds)

    async def _srv_resolve_profile(call) -> None:
        pid = call.data["profile_id"]
        from .profile.store import async_save_profile_from_options
        from .resolver import PreferenceResolver

        await PreferenceResolver(hass).resolve_profile(entry, pid)
        await async_save_profile_from_options(hass, entry, pid)

    async def _srv_resolve_all(call) -> None:
        from .profile.store import async_save_profile_from_options
        from .resolver import PreferenceResolver

        resolver = PreferenceResolver(hass)
        for pid in entry.options.get(CONF_PROFILES, {}):
            await resolver.resolve_profile(entry, pid)
            await async_save_profile_from_options(hass, entry, pid)

    async def _srv_generate_profile(call) -> None:
        pid = call.data["profile_id"]
        raw_mode = str(call.data["mode"]).strip()
        mode = raw_mode.lower()
        if mode not in {"clone", "opb"}:
            _require(FEATURE_AI_ASSIST)
        source_profile_id = call.data.get("source_profile_id")
        from .resolver import generate_profile

        await generate_profile(hass, entry, pid, mode, source_profile_id)

    async def _srv_clear_caches(call) -> None:
        from .ai_client import clear_ai_cache
        from .opb_client import clear_opb_cache

        clear_ai_cache()
        clear_opb_cache()

    _register_service(
        SERVICE_REPLACE_SENSOR,
        _srv_replace_sensor,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("measurement"): vol.In(sorted(MEASUREMENT_CLASSES)),
                vol.Required("entity_id"): ENTITY_ID_SCHEMA,
            }
        ),
    )

    def _validate_link_payload(data: Mapping[str, Any]) -> dict[str, Any]:
        meter_entity = data.get("meter_entity")
        new_sensor = data.get("new_sensor")
        profile_id = data.get("profile_id")
        role = data.get("role")
        entity_id = data.get("entity_id")

        if meter_entity or new_sensor:
            if not meter_entity or not new_sensor:
                raise vol.Invalid("Both meter_entity and new_sensor must be provided")
            return {
                "meter_entity": meter_entity,
                "new_sensor": new_sensor,
            }

        if not (profile_id and role and entity_id):
            raise vol.Invalid("Provide meter_entity/new_sensor or profile_id/entity_id/role")

        return {
            "profile_id": profile_id,
            "role": role,
            "entity_id": entity_id,
        }

    _register_service(
        SERVICE_LINK_SENSOR,
        _srv_link_sensor,
        schema=vol.All(
            vol.Schema(
                {
                    vol.Optional("profile_id"): str,
                    vol.Optional("entity_id"): ENTITY_ID_SCHEMA,
                    vol.Optional("role"): vol.In(
                        [
                            "temperature",
                            "humidity",
                            "soil_moisture",
                            "illuminance",
                            "co2",
                            "ph",
                        ]
                    ),
                    vol.Optional("meter_entity"): ENTITY_ID_SCHEMA,
                    vol.Optional("new_sensor"): ENTITY_ID_SCHEMA,
                }
            ),
            _validate_link_payload,
        ),
    )
    _register_service(
        SERVICE_REFRESH_SPECIES,
        _srv_refresh_species,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    _register_service(
        SERVICE_CREATE_PROFILE,
        _srv_create_profile,
        schema=vol.Schema({vol.Required("name"): str}),
    )
    _register_service(
        SERVICE_DUPLICATE_PROFILE,
        _srv_duplicate_profile,
        schema=vol.Schema({vol.Required("source_profile_id"): str, vol.Required("new_name"): str}),
    )
    _register_service(
        SERVICE_DELETE_PROFILE,
        _srv_delete_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    _register_service(
        SERVICE_UPDATE_SENSORS,
        _srv_update_sensors,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("temperature"): ENTITY_ID_SCHEMA,
                vol.Optional("humidity"): ENTITY_ID_SCHEMA,
                vol.Optional("illuminance"): ENTITY_ID_SCHEMA,
                vol.Optional("moisture"): ENTITY_ID_SCHEMA,
                vol.Optional("co2"): ENTITY_ID_SCHEMA,
                vol.Optional("ph"): ENTITY_ID_SCHEMA,
            }
        ),
    )
    _register_service(
        SERVICE_EXPORT_PROFILES,
        _srv_export_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    _register_service(
        SERVICE_EXPORT_PROFILE,
        _srv_export_profile,
        schema=vol.Schema({vol.Required("profile_id"): str, vol.Required("path"): str}),
    )
    _register_service(
        SERVICE_RECORD_RUN_EVENT,
        _srv_record_run_event,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("run_id"): str,
                vol.Required("started_at"): str,
                vol.Optional("species_id"): str,
                vol.Optional("ended_at"): str,
                vol.Optional("environment"): dict,
                vol.Optional("metadata"): dict,
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_RECORD_HARVEST_EVENT,
        _srv_record_harvest_event,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("harvest_id"): str,
                vol.Required("harvested_at"): str,
                vol.Required("yield_grams"): vol.Coerce(float),
                vol.Optional("species_id"): str,
                vol.Optional("run_id"): str,
                vol.Optional("area_m2"): vol.Coerce(float),
                vol.Optional("wet_weight_grams"): vol.Coerce(float),
                vol.Optional("dry_weight_grams"): vol.Coerce(float),
                vol.Optional("fruit_count"): vol.Coerce(int),
                vol.Optional("metadata"): dict,
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_RECORD_NUTRIENT_EVENT,
        _srv_record_nutrient_event,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("event_id"): str,
                vol.Required("applied_at"): str,
                vol.Optional("species_id"): str,
                vol.Optional("run_id"): str,
                vol.Optional("product_id"): str,
                vol.Optional("product_name"): str,
                vol.Optional("product_category"): str,
                vol.Optional("source"): str,
                vol.Optional("solution_volume_liters"): vol.Coerce(float),
                vol.Optional("concentration_ppm"): vol.Coerce(float),
                vol.Optional("ec_ms"): vol.Coerce(float),
                vol.Optional("ph"): vol.Coerce(float),
                vol.Optional("additives"): list,
                vol.Optional("metadata"): dict,
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_RECORD_CULTIVATION_EVENT,
        _srv_record_cultivation_event,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("event_id"): str,
                vol.Required("occurred_at"): str,
                vol.Required("event_type"): str,
                vol.Optional("species_id"): str,
                vol.Optional("run_id"): str,
                vol.Optional("title"): str,
                vol.Optional("notes"): str,
                vol.Optional("metric_value"): vol.Coerce(float),
                vol.Optional("metric_unit"): str,
                vol.Optional("actor"): str,
                vol.Optional("location"): str,
                vol.Optional("tags"): list,
                vol.Optional("metadata"): dict,
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_PROFILE_PROVENANCE,
        _srv_profile_provenance,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("include_overlay", default=False): bool,
                vol.Optional("include_extras", default=False): bool,
                vol.Optional("include_citations", default=False): bool,
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_PROFILE_RUNS,
        _srv_profile_runs,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("limit"): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_IMPORT_PROFILES,
        _srv_import_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    _register_service(
        SERVICE_IMPORT_TEMPLATE,
        _srv_import_template,
        schema=vol.Schema({vol.Required("template"): str, vol.Optional("name"): str}),
    )
    _register_service(
        SERVICE_CLOUD_LOGIN,
        _srv_cloud_login,
        schema=vol.Schema(
            {
                vol.Optional("base_url"): str,
                vol.Required("email"): str,
                vol.Required("password"): str,
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_CLOUD_LOGOUT,
        _srv_cloud_logout,
        schema=vol.Schema({}),
        supports_response=True,
    )
    _register_service(
        SERVICE_CLOUD_SELECT_ORG,
        _srv_cloud_select_org,
        schema=vol.Schema(
            {
                vol.Optional("organization_id"): str,
                vol.Optional("organization_name"): str,
                vol.Optional("role"): str,
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_CLOUD_REFRESH,
        _srv_cloud_refresh,
        schema=vol.Schema({vol.Optional("base_url"): str}),
        supports_response=True,
    )
    _register_service(
        SERVICE_CLOUD_SYNC_NOW,
        _srv_cloud_sync_now,
        schema=vol.Schema(
            {
                vol.Optional("push", default=True): vol.Boolean(),
                vol.Optional("pull", default=True): vol.Boolean(),
            }
        ),
        supports_response=True,
    )
    _register_service(
        SERVICE_REFRESH,
        _srv_refresh,
        schema=vol.Schema({}),
    )
    _register_service(
        SERVICE_RECOMPUTE,
        _srv_recompute,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    _register_service(
        SERVICE_RESET_DLI,
        _srv_reset_dli,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    _register_service(
        SERVICE_RECOMMEND_WATERING,
        _srv_recommend_watering,
        schema=vol.Schema({vol.Required("profile_id"): str}),
        supports_response=True,
    )
    _register_service(
        SERVICE_RECALCULATE_TARGETS,
        _srv_recalculate_targets,
        schema=vol.Schema({vol.Required("plant_id"): str}),
    )
    _register_service(
        SERVICE_RUN_RECOMMENDATION,
        _srv_run_recommendation,
        schema=vol.Schema(
            {
                vol.Required("plant_id"): str,
                vol.Optional("approve", default=False): bool,
            }
        ),
    )
    _register_service(
        SERVICE_APPLY_IRRIGATION_PLAN,
        _srv_apply_irrigation,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("provider", default="auto"): vol.In(["auto", "irrigation_unlimited", "opensprinkler"]),
                vol.Optional("zone"): str,
            }
        ),
    )
    _register_service(
        SERVICE_RESOLVE_PROFILE,
        _srv_resolve_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    _register_service(SERVICE_RESOLVE_ALL, _srv_resolve_all)
    _register_service(
        SERVICE_GENERATE_PROFILE,
        _srv_generate_profile,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("mode"): vol.In(["clone", "opb", "ai"]),
                vol.Optional("source_profile_id"): str,
            }
        ),
    )
    _register_service(SERVICE_CLEAR_CACHES, _srv_clear_caches)

    # Preserve backwards compatible top-level sensors mapping if it exists.
    # This mirrors the behaviour of earlier versions of the integration where
    # sensors were stored directly under ``entry.options['sensors']``.
    if entry.options.get("sensors") and CONF_PROFILES not in entry.options:
        _LOGGER.debug("Migrating legacy sensors mapping into profile registry")
        profile_id = entry.options.get("plant_id", "profile")
        profiles = dict(entry.options.get(CONF_PROFILES, {}))
        profiles[profile_id] = {
            "name": entry.title or profile_id,
            "sensors": dict(entry.options.get("sensors")),
            "plant_id": profile_id,
        }
        new_opts = dict(entry.options)
        new_opts[CONF_PROFILES] = profiles
        hass.config_entries.async_update_entry(entry, options=new_opts)
        entry.options = new_opts


async def async_unload_services(hass: HomeAssistant) -> None:
    """Remove registered profile services."""

    for name in SERVICE_NAMES:
        if hass.services.has_service(DOMAIN, name):
            hass.services.async_remove(DOMAIN, name)


def async_setup_services(_hass: HomeAssistant) -> None:  # pragma: no cover - legacy shim
    """Maintain compatibility with older entry setup code."""
    return None
