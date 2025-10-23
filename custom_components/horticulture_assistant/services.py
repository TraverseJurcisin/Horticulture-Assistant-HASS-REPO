"""Service handlers for Horticulture Assistant.

These services expose high level operations for manipulating plant profiles
at runtime. They are intentionally lightweight wrappers around the
:class:`ProfileRegistry` to keep the integration's ``__init__`` module from
becoming monolithic.
"""

from __future__ import annotations

import contextlib
import logging
import types
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Final

import voluptuous as vol
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError

if TYPE_CHECKING:  # pragma: no cover - imported for type checkers only
    from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
    from homeassistant.helpers import config_validation as cv
    from homeassistant.helpers import entity_registry as er
    from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
else:
    try:  # pragma: no cover - exercised during runtime
        from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
    except Exception:  # pragma: no cover - fallback when Home Assistant not installed
        HomeAssistant = Any  # type: ignore[assignment]
        ServiceCall = Any  # type: ignore[assignment]
        ServiceResponse = Any  # type: ignore[assignment]

    try:  # pragma: no cover - exercised during runtime
        from homeassistant.helpers import config_validation as cv  # type: ignore[assignment]
    except Exception:  # pragma: no cover - fallback for standalone tests
        cv = types.SimpleNamespace(entity_id=lambda value: value)  # type: ignore[assignment]

    try:  # pragma: no cover - exercised during runtime
        from homeassistant.helpers import entity_registry as er  # type: ignore[assignment]
    except Exception:  # pragma: no cover - fallback for standalone tests
        er = types.SimpleNamespace()

    try:  # pragma: no cover - exercised during runtime
        from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
    except Exception:  # pragma: no cover - fallback for standalone tests
        DataUpdateCoordinator = Any  # type: ignore[assignment]
        UpdateFailed = Any  # type: ignore[assignment]

from .const import CONF_PROFILES, DOMAIN
from .irrigation_bridge import async_apply_irrigation
from .profile.statistics import SUCCESS_STATS_VERSION
from .profile_registry import ProfileRegistry
from .storage import LocalStore

_LOGGER = logging.getLogger(__name__)
_MISSING: Final = object()

# Mapping of measurement names to expected device classes.  These roughly
# correspond to the roles supported by :mod:`update_sensors`.
MEASUREMENT_CLASSES: Final = {
    "temperature": SensorDeviceClass.TEMPERATURE,
    "humidity": SensorDeviceClass.HUMIDITY,
    "illuminance": SensorDeviceClass.ILLUMINANCE,
    "moisture": SensorDeviceClass.MOISTURE,
    "co2": SensorDeviceClass.CO2,
    "ph": SensorDeviceClass.PH,
}

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
SERVICE_PROFILE_PROVENANCE = "profile_provenance"

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
    SERVICE_PROFILE_PROVENANCE,
)


async def async_register_all(
    hass: HomeAssistant,
    entry: ConfigEntry,
    ai_coord: DataUpdateCoordinator | None,
    local_coord: DataUpdateCoordinator | None,
    profile_coord: DataUpdateCoordinator | None,
    registry: ProfileRegistry,
    store: LocalStore,
) -> None:
    """Register high level profile services."""

    async def _refresh_profile() -> None:
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_replace_sensor(call) -> None:
        profile_id: str = call.data["profile_id"]
        measurement: str = call.data["measurement"]
        entity_id: str = call.data["entity_id"]

        if measurement not in MEASUREMENT_CLASSES:
            raise HomeAssistantError(f"unknown measurement {measurement}")
        if hass.states.get(entity_id) is None:
            raise HomeAssistantError(f"missing entity {entity_id}")

        reg = er.async_get(hass)
        reg_entry = reg.async_get(entity_id)
        expected = MEASUREMENT_CLASSES[measurement]
        if reg_entry:
            actual = reg_entry.device_class or reg_entry.original_device_class
            if expected and actual != expected.value:
                raise HomeAssistantError("device class mismatch")
        try:
            await registry.async_replace_sensor(profile_id, measurement, entity_id)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await _refresh_profile()

    async def _srv_link_sensor(call) -> None:
        profile_id: str = call.data["profile_id"]
        role: str = call.data["role"]
        entity_id: str = call.data["entity_id"]

        measurement = "moisture" if role == "soil_moisture" else role
        if measurement not in MEASUREMENT_CLASSES:
            raise HomeAssistantError(f"unknown role {role}")
        if hass.states.get(entity_id) is None:
            raise HomeAssistantError(f"missing entity {entity_id}")

        reg = er.async_get(hass)
        reg_entry = reg.async_get(entity_id)
        expected = MEASUREMENT_CLASSES[measurement]
        if reg_entry:
            actual = reg_entry.device_class or reg_entry.original_device_class
            if expected and actual != expected.value:
                raise HomeAssistantError("device class mismatch")

        try:
            await registry.async_replace_sensor(profile_id, measurement, entity_id)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err
        await _refresh_profile()

    async def _srv_refresh_species(call) -> None:
        profile_id: str = call.data["profile_id"]
        try:
            await registry.async_refresh_species(profile_id)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

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
        for role in ("temperature", "humidity", "illuminance", "moisture"):
            if ent := call.data.get(role):
                if hass.states.get(ent) is None:
                    raise HomeAssistantError(f"missing entity {ent}")
                sensors[role] = ent
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
        if profile.last_resolved:
            response["last_resolved"] = profile.last_resolved
        return response

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
        if ai_coord:
            await ai_coord.async_request_refresh()
        if local_coord:
            await local_coord.async_request_refresh()
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_recompute(call) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_id:
            profiles = entry.options.get(CONF_PROFILES, {})
            if profile_id not in profiles:
                raise HomeAssistantError(f"unknown profile {profile_id}")
        if profile_coord:
            await profile_coord.async_request_refresh()

    async def _srv_reset_dli(call: ServiceCall) -> None:
        profile_id: str | None = call.data.get("profile_id")
        if profile_coord:
            await profile_coord.async_reset_dli(profile_id)

    async def _srv_recommend_watering(call: ServiceCall) -> ServiceResponse:
        """Suggest a watering duration based on profile metrics."""

        pid: str = call.data["profile_id"]
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
        if local_coord:
            await local_coord.async_request_refresh()

    async def _srv_run_recommendation(call) -> None:
        plant_id = call.data["plant_id"]
        assert store.data is not None
        plants = store.data.setdefault("plants", {})
        if plant_id not in plants:
            raise HomeAssistantError(f"unknown plant {plant_id}")
        prev = _MISSING
        if ai_coord and isinstance(ai_coord.data, Mapping):
            prev = ai_coord.data.get("recommendation", _MISSING)
        if ai_coord:
            with contextlib.suppress(UpdateFailed):
                await ai_coord.async_request_refresh()
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
        provider = call.data.get("provider", "auto")
        zone = call.data.get("zone")
        reg = er.async_get(hass)
        unique_id = f"{DOMAIN}_{entry.entry_id}_{profile_id}_irrigation_rec"
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
        mode = call.data["mode"]
        source_profile_id = call.data.get("source_profile_id")
        from .resolver import generate_profile

        await generate_profile(hass, entry, pid, mode, source_profile_id)

    async def _srv_clear_caches(call) -> None:
        from .ai_client import clear_ai_cache
        from .opb_client import clear_opb_cache

        clear_ai_cache()
        clear_opb_cache()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REPLACE_SENSOR,
        _srv_replace_sensor,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("measurement"): vol.In(sorted(MEASUREMENT_CLASSES)),
                vol.Required("entity_id"): cv.entity_id,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_LINK_SENSOR,
        _srv_link_sensor,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Required("entity_id"): cv.entity_id,
                vol.Required("role"): vol.In(
                    [
                        "temperature",
                        "humidity",
                        "soil_moisture",
                        "illuminance",
                        "co2",
                        "ph",
                    ]
                ),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_SPECIES,
        _srv_refresh_species,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_PROFILE,
        _srv_create_profile,
        schema=vol.Schema({vol.Required("name"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DUPLICATE_PROFILE,
        _srv_duplicate_profile,
        schema=vol.Schema({vol.Required("source_profile_id"): str, vol.Required("new_name"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_PROFILE,
        _srv_delete_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_SENSORS,
        _srv_update_sensors,
        schema=vol.Schema(
            {
                vol.Required("profile_id"): str,
                vol.Optional("temperature"): cv.entity_id,
                vol.Optional("humidity"): cv.entity_id,
                vol.Optional("illuminance"): cv.entity_id,
                vol.Optional("moisture"): cv.entity_id,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_PROFILES,
        _srv_export_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_EXPORT_PROFILE,
        _srv_export_profile,
        schema=vol.Schema({vol.Required("profile_id"): str, vol.Required("path"): str}),
    )
    hass.services.async_register(
        DOMAIN,
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
    hass.services.async_register(
        DOMAIN,
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
    hass.services.async_register(
        DOMAIN,
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_PROFILES,
        _srv_import_profiles,
        schema=vol.Schema({vol.Required("path"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_IMPORT_TEMPLATE,
        _srv_import_template,
        schema=vol.Schema({vol.Required("template"): str, vol.Optional("name"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        _srv_refresh,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECOMPUTE,
        _srv_recompute,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_DLI,
        _srv_reset_dli,
        schema=vol.Schema({vol.Optional("profile_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECOMMEND_WATERING,
        _srv_recommend_watering,
        schema=vol.Schema({vol.Required("profile_id"): str}),
        supports_response=True,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RECALCULATE_TARGETS,
        _srv_recalculate_targets,
        schema=vol.Schema({vol.Required("plant_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RUN_RECOMMENDATION,
        _srv_run_recommendation,
        schema=vol.Schema(
            {
                vol.Required("plant_id"): str,
                vol.Optional("approve", default=False): bool,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
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
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESOLVE_PROFILE,
        _srv_resolve_profile,
        schema=vol.Schema({vol.Required("profile_id"): str}),
    )
    hass.services.async_register(DOMAIN, SERVICE_RESOLVE_ALL, _srv_resolve_all)
    hass.services.async_register(
        DOMAIN,
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
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_CACHES, _srv_clear_caches)

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
