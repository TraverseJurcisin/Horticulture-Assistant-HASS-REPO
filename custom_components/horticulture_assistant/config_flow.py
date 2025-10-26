from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector as sel

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_SYNC_INTERVAL,
    CONF_CLOUD_TENANT_ID,
    CONF_CO2_SENSOR,
    CONF_EC_SENSOR,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_MOISTURE_SENSOR,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PLANT_TYPE,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    CONF_TEMPERATURE_SENSOR,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_CLOUD_SYNC_INTERVAL,
    DEFAULT_KEEP_STALE,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    PROFILE_SCOPE_CHOICES,
    PROFILE_SCOPE_DEFAULT,
)
from .opb_client import OpenPlantbookClient
from .profile.compat import sync_thresholds
from .profile.utils import determine_species_slug, ensure_sections
from .profile.validation import evaluate_threshold_bounds
from .sensor_catalog import collect_sensor_suggestions, format_sensor_hints
from .sensor_validation import collate_issue_messages, validate_sensor_links
from .utils import profile_generator
from .utils.entry_helpers import get_primary_profile_id
from .utils.json_io import load_json, save_json
from .utils.nutrient_schedule import generate_nutrient_schedule
from .utils.plant_registry import register_plant

_LOGGER = logging.getLogger(__name__)

PROFILE_SCOPE_LABELS = {
    "individual": "Individual plant (single specimen)",
    "species_template": "Species template (reusable baseline)",
    "crop_batch": "Crop batch or bed (shared conditions)",
    "grow_zone": "Grow zone or environment",
}
PROFILE_SCOPE_SELECTOR_OPTIONS = [
    {"value": value, "label": PROFILE_SCOPE_LABELS[value]} for value in PROFILE_SCOPE_CHOICES
]

MANUAL_THRESHOLD_FIELDS = (
    "temperature_min",
    "temperature_max",
    "humidity_min",
    "humidity_max",
    "illuminance_min",
    "illuminance_max",
    "conductivity_min",
    "conductivity_max",
)


SENSOR_OPTION_ROLES = {
    CONF_MOISTURE_SENSOR: "moisture",
    CONF_TEMPERATURE_SENSOR: "temperature",
    CONF_EC_SENSOR: "ec",
    CONF_CO2_SENSOR: "co2",
}

SENSOR_OPTION_FALLBACKS = {
    CONF_MOISTURE_SENSOR: sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])),
    CONF_TEMPERATURE_SENSOR: sel.EntitySelector(
        sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])
    ),
    CONF_EC_SENSOR: sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"])),
    CONF_CO2_SENSOR: sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["carbon_dioxide"])),
}

PROFILE_SENSOR_FIELDS = {
    "temperature": sel.EntitySelector(
        sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])
    ),
    "humidity": sel.EntitySelector(
        sel.EntitySelectorConfig(domain=["sensor"], device_class=["humidity"])
    ),
    "illuminance": sel.EntitySelector(
        sel.EntitySelectorConfig(domain=["sensor"], device_class=["illuminance"])
    ),
    "moisture": sel.EntitySelector(
        sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])
    ),
    "conductivity": sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"])),
    "co2": sel.EntitySelector(
        sel.EntitySelectorConfig(domain=["sensor"], device_class=["carbon_dioxide"])
    ),
}


def _build_sensor_schema(hass, defaults: Mapping[str, Any] | None = None):
    """Return a voluptuous schema and hint placeholders for sensor selection."""

    defaults = defaults or {}
    suggestions = collect_sensor_suggestions(
        hass,
        SENSOR_OPTION_ROLES.values(),
        limit=6,
    )
    role_map = {role: suggestions.get(role, []) for role in sorted(set(SENSOR_OPTION_ROLES.values()))}
    placeholders = {"sensor_hints": format_sensor_hints(role_map)}

    schema_fields: dict[Any, Any] = {}
    for option_key, role in SENSOR_OPTION_ROLES.items():
        default_value = defaults.get(option_key)
        if default_value is None:
            optional = vol.Optional(option_key)
        else:
            optional = vol.Optional(option_key, default=default_value)
        options = suggestions.get(role, [])
        if options:
            selector = sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=[
                        {"value": suggestion.entity_id, "label": f"{suggestion.name} ({suggestion.entity_id})"}
                        for suggestion in options
                    ],
                    custom_value=True,
                )
            )
        else:
            selector = SENSOR_OPTION_FALLBACKS[option_key]
        schema_fields[optional] = vol.Any(selector, str)

    return vol.Schema(schema_fields), placeholders


PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLANT_NAME): cv.string,
        vol.Optional(CONF_PLANT_TYPE): cv.string,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc,call-arg]
    VERSION = 3

    def __init__(self) -> None:
        self._config: dict | None = None
        self._profile: dict | None = None
        self._thresholds: dict[str, float] = {}
        self._opb_credentials: dict[str, str] | None = None
        self._opb_results: list[dict[str, str]] = []
        self._species_pid: str | None = None
        self._species_display: str | None = None
        self._image_url: str | None = None

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        self._config = {}
        return await self.async_step_profile(user_input)

    async def async_step_profile(self, user_input=None):
        errors = {}
        if user_input is not None and self._config is not None:
            plant_name = user_input[CONF_PLANT_NAME].strip()
            plant_type = user_input.get(CONF_PLANT_TYPE, "").strip()
            if not plant_name:
                errors[CONF_PLANT_NAME] = "required"
            else:
                metadata = {CONF_PLANT_NAME: plant_name}
                if plant_type:
                    metadata[CONF_PLANT_TYPE] = plant_type
                try:
                    plant_id = await self.hass.async_add_executor_job(
                        profile_generator.generate_profile,
                        metadata,
                        self.hass,
                    )
                except Exception as err:  # pragma: no cover - unexpected
                    errors["base"] = "profile_error"
                    _LOGGER.exception("Failed to generate profile: %s", err)
                else:
                    if not plant_id:
                        errors["base"] = "profile_error"
            if not errors:
                self._profile = {
                    CONF_PLANT_ID: plant_id,
                    CONF_PLANT_NAME: plant_name,
                }
                if plant_type:
                    self._profile[CONF_PLANT_TYPE] = plant_type
                return await self.async_step_threshold_source()
        return self.async_show_form(step_id="profile", data_schema=PROFILE_SCHEMA, errors=errors)

    async def async_step_threshold_source(self, user_input=None):
        if self._profile is None:
            _LOGGER.debug("Profile metadata missing when selecting threshold source; returning to profile step.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()
        if user_input is not None:
            method = user_input["method"]
            if method == "openplantbook":
                return await self.async_step_opb_credentials()
            if method == "skip":
                self._thresholds = {}
                self._species_display = None
                self._species_pid = None
                self._image_url = None
                return await self._complete_profile({})
            return await self.async_step_thresholds()
        schema = vol.Schema(
            {
                vol.Required("method", default="manual"): sel.SelectSelector(
                    sel.SelectSelectorConfig(
                        options=[
                            {"value": "openplantbook", "label": "From OpenPlantbook"},
                            {"value": "manual", "label": "Manual entry"},
                            {"value": "skip", "label": "Skip for now"},
                        ]
                    )
                )
            }
        )
        return self.async_show_form(step_id="threshold_source", data_schema=schema)

    async def async_step_opb_credentials(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                OpenPlantbookClient(self.hass, user_input["client_id"], user_input["secret"])
            except RuntimeError:
                errors["base"] = "opb_missing"
            else:
                self._opb_credentials = {
                    "client_id": user_input["client_id"],
                    "secret": user_input["secret"],
                }
                return await self.async_step_opb_species_search()
        return self.async_show_form(
            step_id="opb_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required("client_id"): str,
                    vol.Required("secret"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_opb_species_search(self, user_input=None):
        if self._opb_credentials is None:
            return self.async_abort(reason="unknown")
        client = OpenPlantbookClient(self.hass, self._opb_credentials["client_id"], self._opb_credentials["secret"])
        if user_input is not None:
            try:
                results = await client.search(user_input["query"])
            except Exception as err:  # pragma: no cover - network issues
                _LOGGER.warning("OpenPlantbook search failed: %s", err)
                return await self.async_step_thresholds()
            if not results:
                return await self.async_step_thresholds()
            self._opb_results = results
            return await self.async_step_opb_species_select()
        schema = vol.Schema({vol.Required("query"): str})
        return self.async_show_form(step_id="opb_species_search", data_schema=schema)

    async def async_step_opb_species_select(self, user_input=None):
        if self._opb_credentials is None:
            return self.async_abort(reason="unknown")
        client = OpenPlantbookClient(self.hass, self._opb_credentials["client_id"], self._opb_credentials["secret"])
        results = self._opb_results
        if user_input is not None:
            pid = user_input["pid"]
            try:
                detail = await client.get_details(pid)
            except Exception as err:  # pragma: no cover - network issues
                _LOGGER.warning("OpenPlantbook details failed: %s", err)
                return await self.async_step_thresholds()
            self._species_pid = pid
            self._species_display = next((r["display"] for r in results if r["pid"] == pid), pid)
            thresholds = {
                "temperature_min": detail.get("min_temp"),
                "temperature_max": detail.get("max_temp"),
                "humidity_min": detail.get("min_hum"),
                "humidity_max": detail.get("max_hum"),
                "illuminance_min": detail.get("min_lux"),
                "illuminance_max": detail.get("max_lux"),
                "conductivity_min": detail.get("min_soil_ec"),
                "conductivity_max": detail.get("max_soil_ec"),
            }
            self._thresholds = {k: v for k, v in thresholds.items() if v is not None}
            image_url = detail.get("image_url") or detail.get("image")
            self._image_url = image_url
            if image_url:
                auto_dl = True
                dl_path = Path(self.hass.config.path("www/images/plants"))
                existing = self._async_current_entries()
                if existing:
                    opts = existing[0].options
                    auto_dl = opts.get("opb_auto_download_images", True)
                    dl_path = Path(opts.get("opb_download_dir", dl_path))
                if auto_dl:
                    name = self._profile.get(CONF_PLANT_NAME, "") if self._profile else ""
                    local_url = await client.download_image(name, image_url, dl_path)
                    if local_url:
                        self._image_url = local_url
            return await self.async_step_thresholds()
        schema = vol.Schema(
            {
                vol.Required("pid"): sel.SelectSelector(
                    sel.SelectSelectorConfig(options=[{"value": r["pid"], "label": r["display"]} for r in results])
                )
            }
        )
        return self.async_show_form(step_id="opb_species_select", data_schema=schema)

    async def async_step_thresholds(self, user_input=None):
        if self._profile is None:
            _LOGGER.debug("Profile metadata missing at thresholds step; returning to profile form.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()

        defaults = self._thresholds
        schema_fields: dict[Any, Any] = {}
        for key in MANUAL_THRESHOLD_FIELDS:
            default = defaults.get(key)
            option = vol.Optional(key, default=str(default) if default is not None else "")
            schema_fields[option] = vol.Any(str, int, float)
        schema = vol.Schema(schema_fields, extra=vol.ALLOW_EXTRA)

        if user_input is not None:
            errors: dict[str, str] = {}
            cleaned: dict[str, float] = {}
            for key in MANUAL_THRESHOLD_FIELDS:
                raw = user_input.get(key)
                if raw in (None, "", []):
                    continue
                try:
                    cleaned[key] = float(raw)
                except (TypeError, ValueError):
                    errors[key] = "invalid_float"
            if errors:
                return self.async_show_form(step_id="thresholds", data_schema=schema, errors=errors)

            violations = evaluate_threshold_bounds(cleaned)
            if violations:
                error_summary = [violation.message() for violation in violations[:3]]
                if len(violations) > 3:
                    error_summary.append(f"(+{len(violations) - 3} more)")
                placeholders = {"issue_detail": "\n".join(error_summary)}
                field_errors = {issue.key: "threshold_field_error" for issue in violations}
                field_errors["base"] = "threshold_out_of_bounds"
                return self.async_show_form(
                    step_id="thresholds",
                    data_schema=schema,
                    errors=field_errors,
                    description_placeholders=placeholders,
                )
            self._thresholds = cleaned
            return await self.async_step_sensors()

        return self.async_show_form(step_id="thresholds", data_schema=schema)

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._profile is None:
            _LOGGER.debug("Profile metadata missing at sensors step; returning to profile form.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()

        schema, placeholders = _build_sensor_schema(self.hass)

        errors = {}
        if user_input is not None:
            for key in (
                CONF_MOISTURE_SENSOR,
                CONF_TEMPERATURE_SENSOR,
                CONF_EC_SENSOR,
                CONF_CO2_SENSOR,
            ):
                entity_id = user_input.get(key)
                if entity_id and self.hass.states.get(entity_id) is None:
                    errors[key] = "not_found"
            if errors:
                return self.async_show_form(
                    step_id="sensors", data_schema=schema, errors=errors, description_placeholders=placeholders
                )
            return await self._complete_profile(user_input)

        return self.async_show_form(step_id="sensors", data_schema=schema, description_placeholders=placeholders)

    async def _complete_profile(self, user_input: dict[str, Any]) -> FlowResult:
        if self._profile is None:
            _LOGGER.debug("Attempted to complete profile without metadata; restarting profile step.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()

        sensor_map: dict[str, list[str]] = {}
        if moisture := user_input.get(CONF_MOISTURE_SENSOR):
            sensor_map["moisture_sensors"] = [moisture]
        if temperature := user_input.get(CONF_TEMPERATURE_SENSOR):
            sensor_map["temperature_sensors"] = [temperature]
        if ec := user_input.get(CONF_EC_SENSOR):
            sensor_map["ec_sensors"] = [ec]
        if co2 := user_input.get(CONF_CO2_SENSOR):
            sensor_map["co2_sensors"] = [co2]
        if sensor_map:
            plant_id = self._profile[CONF_PLANT_ID]

            def _save_sensors():
                path = self.hass.config.path("plants", plant_id, "general.json")
                try:
                    data = load_json(path)
                except Exception:
                    data = {}
                container = data.setdefault("sensor_entities", {})
                for key, value in sensor_map.items():
                    container[key] = value
                save_json(path, data)

            await self.hass.async_add_executor_job(_save_sensors)
        plant_id = self._profile[CONF_PLANT_ID]
        await self.hass.async_add_executor_job(
            register_plant,
            plant_id,
            {
                "display_name": self._profile[CONF_PLANT_NAME],
                "profile_path": f"plants/{plant_id}/general.json",
                **({"plant_type": self._profile[CONF_PLANT_TYPE]} if self._profile.get(CONF_PLANT_TYPE) else {}),
            },
            self.hass,
        )
        mapped: dict[str, str] = {}
        if moisture := user_input.get(CONF_MOISTURE_SENSOR):
            mapped["moisture"] = moisture
        if temperature := user_input.get(CONF_TEMPERATURE_SENSOR):
            mapped["temperature"] = temperature
        if ec := user_input.get(CONF_EC_SENSOR):
            mapped["conductivity"] = ec
        if co2 := user_input.get(CONF_CO2_SENSOR):
            mapped["co2"] = co2

        profile_name = self._profile[CONF_PLANT_NAME]
        plant_id = self._profile[CONF_PLANT_ID]
        general_section: dict[str, Any] = {}
        if mapped:
            general_section["sensors"] = dict(mapped)
        if plant_type := self._profile.get(CONF_PLANT_TYPE):
            general_section.setdefault("plant_type", plant_type)
        general_section.setdefault(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)

        thresholds_payload = {"thresholds": dict(self._thresholds)}
        sync_thresholds(thresholds_payload, default_source="manual")

        profile_entry: dict[str, Any] = {
            "name": profile_name,
            "plant_id": plant_id,
            "sensors": dict(mapped),
            "thresholds": thresholds_payload["thresholds"],
            "resolved_targets": thresholds_payload["resolved_targets"],
            "variables": thresholds_payload["variables"],
        }
        if general_section:
            profile_entry["general"] = general_section
        if sections := thresholds_payload.get("sections"):
            profile_entry["sections"] = sections
        if self._species_display:
            profile_entry["species_display"] = self._species_display
        if self._species_pid:
            profile_entry["species_pid"] = self._species_pid
        if self._image_url:
            profile_entry["image_url"] = self._image_url
        if self._opb_credentials:
            profile_entry["opb_credentials"] = self._opb_credentials

        ensure_sections(profile_entry, plant_id=plant_id, display_name=profile_name)

        data = {**(self._config or {}), **self._profile}
        options = dict(user_input)
        options["sensors"] = dict(mapped)
        options["thresholds"] = thresholds_payload["thresholds"]
        options["resolved_targets"] = thresholds_payload["resolved_targets"]
        options["variables"] = thresholds_payload["variables"]
        options[CONF_PROFILES] = {plant_id: profile_entry}
        if self._species_display:
            options["species_display"] = self._species_display
        if self._species_pid:
            options["species_pid"] = self._species_pid
        if self._image_url:
            options["image_url"] = self._image_url
        if self._opb_credentials:
            options["opb_credentials"] = self._opb_credentials
        return self.async_create_entry(title=profile_name, data=data, options=options)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self.config_entry = entry
        self._pid: str | None = None
        self._var: str | None = None
        self._mode: str | None = None
        self._cal_session: str | None = None
        self._new_profile_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "basic",
                "cloud_sync",
                "add_profile",
                "manage_profiles",
                "configure_ai",
                "profile_targets",
                "nutrient_schedule",
            ],
        )

    async def _async_get_registry(self):
        from .profile_registry import ProfileRegistry

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        registry: ProfileRegistry | None = domain_data.get("registry")
        if registry is None:
            registry = ProfileRegistry(self.hass, self._entry)
            await registry.async_initialize()
            domain_data["registry"] = registry
        return registry

    def _notify_sensor_warnings(self, issues) -> None:
        if not issues:
            return
        message = collate_issue_messages(issues)
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Horticulture Assistant sensor warning",
                    "message": message,
                    "notification_id": f"horticulture_sensor_{self._entry.entry_id}",
                },
                blocking=False,
            )
        )

    async def async_step_basic(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        defaults = {
            CONF_MODEL: self._entry.options.get(
                CONF_MODEL,
                self._entry.data.get(CONF_MODEL, DEFAULT_MODEL),
            ),
            CONF_BASE_URL: self._entry.options.get(
                CONF_BASE_URL,
                self._entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            ),
            CONF_UPDATE_INTERVAL: self._entry.options.get(
                CONF_UPDATE_INTERVAL,
                self._entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
            ),
            CONF_KEEP_STALE: self._entry.options.get(
                CONF_KEEP_STALE,
                self._entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
            ),
            "species_display": self._entry.options.get(
                "species_display",
                self._entry.data.get(CONF_PLANT_TYPE, ""),
            ),
            CONF_MOISTURE_SENSOR: self._entry.options.get(CONF_MOISTURE_SENSOR, ""),
            CONF_TEMPERATURE_SENSOR: self._entry.options.get(CONF_TEMPERATURE_SENSOR, ""),
            CONF_EC_SENSOR: self._entry.options.get(CONF_EC_SENSOR, ""),
            CONF_CO2_SENSOR: self._entry.options.get(CONF_CO2_SENSOR, ""),
            "opb_auto_download_images": self._entry.options.get("opb_auto_download_images", True),
            "opb_download_dir": self._entry.options.get(
                "opb_download_dir",
                self.hass.config.path("www/images/plants"),
            ),
            "opb_location_share": self._entry.options.get("opb_location_share", "off"),
            "opb_enable_upload": self._entry.options.get("opb_enable_upload", False),
        }

        sensor_defaults = {
            CONF_MOISTURE_SENSOR: defaults[CONF_MOISTURE_SENSOR],
            CONF_TEMPERATURE_SENSOR: defaults[CONF_TEMPERATURE_SENSOR],
            CONF_EC_SENSOR: defaults[CONF_EC_SENSOR],
            CONF_CO2_SENSOR: defaults[CONF_CO2_SENSOR],
        }
        sensor_schema, placeholders = _build_sensor_schema(self.hass, sensor_defaults)

        schema_fields: dict[Any, Any] = {
            vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
            vol.Optional(CONF_BASE_URL, default=defaults[CONF_BASE_URL]): str,
            vol.Optional(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): int,
            vol.Optional(CONF_KEEP_STALE, default=defaults[CONF_KEEP_STALE]): bool,
            vol.Optional("species_display", default=defaults["species_display"]): str,
            vol.Optional(
                "opb_auto_download_images",
                default=defaults["opb_auto_download_images"],
            ): bool,
            vol.Optional("opb_download_dir", default=defaults["opb_download_dir"]): str,
            vol.Optional(
                "opb_location_share",
                default=defaults["opb_location_share"],
            ): sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=[
                        {"value": "off", "label": "off"},
                        {"value": "country", "label": "country"},
                        {"value": "coordinates", "label": "coordinates"},
                    ]
                )
            ),
            vol.Optional("opb_enable_upload", default=defaults["opb_enable_upload"]): bool,
            vol.Optional("force_refresh", default=False): bool,
        }
        schema_fields.update(sensor_schema.schema)
        schema = vol.Schema(schema_fields)

        errors = {}
        if user_input is not None:
            for key in (
                CONF_MOISTURE_SENSOR,
                CONF_TEMPERATURE_SENSOR,
                CONF_EC_SENSOR,
                CONF_CO2_SENSOR,
            ):
                entity_id = user_input.get(key)
                if entity_id and self.hass.states.get(entity_id) is None:
                    errors[key] = "not_found"
            sensor_map = {
                SENSOR_OPTION_ROLES[key]: user_input[key] for key in SENSOR_OPTION_ROLES if user_input.get(key)
            }
            if sensor_map:
                validation = validate_sensor_links(self.hass, sensor_map)
                for issue in validation.errors:
                    option_key = next((opt for opt, role in SENSOR_OPTION_ROLES.items() if role == issue.role), None)
                    if option_key:
                        errors[option_key] = issue.issue
                if validation.warnings:
                    self._notify_sensor_warnings(validation.warnings)
            if errors:
                return self.async_show_form(
                    step_id="basic",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders=placeholders,
                )
            sensor_map: dict[str, list[str]] = {}
            if moisture := user_input.get(CONF_MOISTURE_SENSOR):
                sensor_map["moisture_sensors"] = [moisture]
            if temperature := user_input.get(CONF_TEMPERATURE_SENSOR):
                sensor_map["temperature_sensors"] = [temperature]
            if ec := user_input.get(CONF_EC_SENSOR):
                sensor_map["ec_sensors"] = [ec]
            if co2 := user_input.get(CONF_CO2_SENSOR):
                sensor_map["co2_sensors"] = [co2]

            plant_id = self._entry.data.get(CONF_PLANT_ID)
            if plant_id:

                def _save_sensors():
                    path = self.hass.config.path("plants", plant_id, "general.json")
                    try:
                        data = load_json(path)
                    except Exception:
                        data = {}
                    container = data.setdefault("sensor_entities", {})
                    for key in (
                        "moisture_sensors",
                        "temperature_sensors",
                        "ec_sensors",
                        "co2_sensors",
                    ):
                        if key in sensor_map:
                            container[key] = sensor_map[key]
                        else:
                            container.pop(key, None)
                    if not container:
                        data.pop("sensor_entities", None)
                    save_json(path, data)

                await self.hass.async_add_executor_job(_save_sensors)

            opts = dict(self._entry.options)
            mapped = {}
            for key, role in (
                (CONF_MOISTURE_SENSOR, "moisture"),
                (CONF_TEMPERATURE_SENSOR, "temperature"),
                (CONF_EC_SENSOR, "conductivity"),
                (CONF_CO2_SENSOR, "co2"),
            ):
                if key in user_input:
                    value = user_input.get(key)
                    if value:
                        opts[key] = value
                        mapped[role] = value
                    else:
                        opts.pop(key, None)
                else:
                    opts.pop(key, None)
            opts["sensors"] = mapped
            profiles = dict(opts.get(CONF_PROFILES, {}))
            plant_id = self._entry.data.get(CONF_PLANT_ID)
            if plant_id:
                primary = dict(profiles.get(plant_id, {}))
                name = primary.get("name") or self._entry.title or opts.get(CONF_PLANT_NAME) or plant_id
                primary["name"] = name
                primary["plant_id"] = plant_id
                if mapped:
                    primary["sensors"] = dict(mapped)
                else:
                    primary.pop("sensors", None)
                general = dict(primary.get("general", {}))
                if mapped:
                    general["sensors"] = dict(mapped)
                else:
                    general.pop("sensors", None)
                general.setdefault(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)
                species_value = (
                    opts.get("species_display")
                    or self._entry.options.get("species_display")
                    or self._entry.data.get(CONF_PLANT_TYPE)
                )
                if species_value and "plant_type" not in general:
                    general["plant_type"] = species_value
                if general:
                    primary["general"] = general
                elif "general" in primary:
                    primary.pop("general")
                ensure_sections(primary, plant_id=plant_id, display_name=name)
                profiles[plant_id] = primary
                opts[CONF_PROFILES] = profiles
            if "species_display" in user_input:
                value = user_input.get("species_display")
                if value:
                    opts["species_display"] = value
                else:
                    opts.pop("species_display", None)
            opts.update(
                {
                    k: v
                    for k, v in user_input.items()
                    if k
                    not in (
                        CONF_MOISTURE_SENSOR,
                        CONF_TEMPERATURE_SENSOR,
                        CONF_EC_SENSOR,
                        CONF_CO2_SENSOR,
                        "force_refresh",
                        "species_display",
                    )
                }
            )
            if user_input.get("force_refresh"):
                plant_id = self._entry.data.get(CONF_PLANT_ID)
                plant_name = self._entry.data.get(CONF_PLANT_NAME)
                if plant_id and plant_name:
                    metadata = {
                        CONF_PLANT_ID: plant_id,
                        CONF_PLANT_NAME: plant_name,
                    }
                    if species := opts.get("species_display"):
                        metadata[CONF_PLANT_TYPE] = species
                    await self.hass.async_add_executor_job(
                        profile_generator.generate_profile,
                        metadata,
                        self.hass,
                        True,
                    )
            return self.async_create_entry(title="", data=opts)

        return self.async_show_form(
            step_id="basic",
            data_schema=schema,
            description_placeholders=placeholders,
        )

    async def async_step_profile_targets(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._pid = None
        self._var = None
        return await self.async_step_profile(user_input)

    async def async_step_nutrient_schedule(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        profiles = self._profiles()
        if not profiles:
            return self.async_abort(reason="no_profiles")
        if user_input is None or "profile_id" not in user_input:
            return self.async_show_form(
                step_id="nutrient_schedule",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile_id"): vol.In({pid: data["name"] for pid, data in profiles.items()}),
                    }
                ),
            )
        self._pid = user_input["profile_id"]
        return await self.async_step_nutrient_schedule_edit()

    async def async_step_nutrient_schedule_edit(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self._pid:
            return await self.async_step_nutrient_schedule()
        profiles = self._profiles()
        profile = profiles.get(self._pid)
        if profile is None:
            return self.async_abort(reason="unknown_profile")

        existing = self._extract_nutrient_schedule(profile)
        schedule_text = json.dumps(existing, indent=2, ensure_ascii=False) if existing else ""

        schema = vol.Schema(
            {
                vol.Optional("auto_generate", default=False): bool,
                vol.Optional(
                    "schedule",
                    default=schedule_text,
                ): sel.TextSelector(sel.TextSelectorConfig(type="text", multiline=True)),
            }
        )

        errors: dict[str, str] = {}
        description_placeholders = {
            "profile": profile.get("name") or profile.get("display_name") or self._pid,
            "current_count": str(len(existing)),
            "example": json.dumps(
                [
                    {
                        "stage": "vegetative",
                        "duration_days": 14,
                        "totals_mg": {"N": 850.0, "K": 630.0},
                    },
                    {
                        "stage": "flowering",
                        "duration_days": 21,
                        "totals_mg": {"N": 600.0, "P": 420.0, "K": 900.0},
                    },
                ],
                indent=2,
                ensure_ascii=False,
            ),
        }
        try:
            plant_type = self._infer_nutrient_schedule_plant_type(profile)
        except Exception:  # pragma: no cover - defensive guard
            plant_type = None
        description_placeholders["plant_type"] = plant_type or "unknown"

        if user_input is not None:
            schedule_payload: list[dict[str, Any]] | None = None
            if user_input.get("auto_generate"):
                try:
                    schedule_payload = self._generate_schedule_for_profile(profile)
                except Exception:  # pragma: no cover - generation failures are logged via UI
                    errors["auto_generate"] = "generation_failed"
            else:
                raw_text = user_input.get("schedule", "").strip()
                if raw_text:
                    try:
                        loaded = json.loads(raw_text)
                    except json.JSONDecodeError:
                        errors["schedule"] = "invalid_json"
                    else:
                        if isinstance(loaded, list):
                            try:
                                schedule_payload = [self._coerce_schedule_row(item) for item in loaded]
                            except ValueError:
                                errors["schedule"] = "invalid_row"
                        else:
                            errors["schedule"] = "invalid_format"
                else:
                    schedule_payload = []
            if not errors and schedule_payload is not None:
                self._apply_nutrient_schedule(self._pid, schedule_payload)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="nutrient_schedule_edit",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_cloud_sync(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        defaults = {
            CONF_CLOUD_SYNC_ENABLED: bool(self._entry.options.get(CONF_CLOUD_SYNC_ENABLED, False)),
            CONF_CLOUD_BASE_URL: self._entry.options.get(CONF_CLOUD_BASE_URL, ""),
            CONF_CLOUD_TENANT_ID: self._entry.options.get(CONF_CLOUD_TENANT_ID, ""),
            CONF_CLOUD_DEVICE_TOKEN: self._entry.options.get(CONF_CLOUD_DEVICE_TOKEN, ""),
            CONF_CLOUD_SYNC_INTERVAL: self._entry.options.get(CONF_CLOUD_SYNC_INTERVAL, DEFAULT_CLOUD_SYNC_INTERVAL),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_CLOUD_SYNC_ENABLED, default=defaults[CONF_CLOUD_SYNC_ENABLED]): bool,
                vol.Optional(CONF_CLOUD_BASE_URL, default=defaults[CONF_CLOUD_BASE_URL]): str,
                vol.Optional(CONF_CLOUD_TENANT_ID, default=defaults[CONF_CLOUD_TENANT_ID]): str,
                vol.Optional(CONF_CLOUD_DEVICE_TOKEN, default=defaults[CONF_CLOUD_DEVICE_TOKEN]): str,
                vol.Optional(CONF_CLOUD_SYNC_INTERVAL, default=defaults[CONF_CLOUD_SYNC_INTERVAL]): int,
            }
        )

        if user_input is not None:
            opts = dict(self._entry.options)
            enabled = bool(user_input.get(CONF_CLOUD_SYNC_ENABLED, False))
            opts[CONF_CLOUD_SYNC_ENABLED] = enabled

            base_url = str(user_input.get(CONF_CLOUD_BASE_URL, "")).strip()
            tenant_id = str(user_input.get(CONF_CLOUD_TENANT_ID, "")).strip()
            device_token = str(user_input.get(CONF_CLOUD_DEVICE_TOKEN, "")).strip()

            if base_url:
                opts[CONF_CLOUD_BASE_URL] = base_url
            else:
                opts.pop(CONF_CLOUD_BASE_URL, None)

            if tenant_id:
                opts[CONF_CLOUD_TENANT_ID] = tenant_id
            else:
                opts.pop(CONF_CLOUD_TENANT_ID, None)

            if enabled and device_token:
                opts[CONF_CLOUD_DEVICE_TOKEN] = device_token
            else:
                opts.pop(CONF_CLOUD_DEVICE_TOKEN, None)

            interval_value = user_input.get(CONF_CLOUD_SYNC_INTERVAL)
            try:
                interval = max(15, int(interval_value)) if interval_value is not None else None
            except (TypeError, ValueError):
                interval = DEFAULT_CLOUD_SYNC_INTERVAL
            if interval is not None:
                opts[CONF_CLOUD_SYNC_INTERVAL] = interval
            else:
                opts.pop(CONF_CLOUD_SYNC_INTERVAL, None)

            return self.async_create_entry(title="", data=opts)

        return self.async_show_form(step_id="cloud_sync", data_schema=schema)

    async def async_step_add_profile(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        registry = await self._async_get_registry()

        if user_input is not None:
            scope = user_input.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)
            copy_from = user_input.get("copy_from")
            pid = await registry.async_add_profile(user_input["name"], copy_from, scope=scope)

            entry_records = domain_data.setdefault(self._entry.entry_id, {})
            store = entry_records.get("profile_store") if isinstance(entry_records, dict) else None
            if store is not None:
                new_profile = registry.get_profile(pid)
                if new_profile is not None:
                    profile_json = new_profile.to_json()
                    sensors = profile_json.get("general", {}).get("sensors", {})
                    clone_payload = deepcopy(profile_json)
                    general = clone_payload.setdefault("general", {})
                    if isinstance(sensors, dict):
                        general.setdefault("sensors", dict(sensors))
                        clone_payload["sensors"] = dict(sensors)
                    if scope is not None:
                        general[CONF_PROFILE_SCOPE] = scope
                    elif CONF_PROFILE_SCOPE not in general:
                        general[CONF_PROFILE_SCOPE] = PROFILE_SCOPE_DEFAULT
                    clone_payload["name"] = profile_json.get("display_name", user_input["name"])
                    await store.async_create_profile(
                        name=profile_json.get("display_name", user_input["name"]),
                        sensors=sensors,
                        clone_from=clone_payload,
                        scope=scope,
                    )
            self._new_profile_id = pid
            return await self.async_step_attach_sensors()
        profiles = {p.plant_id: p.display_name for p in registry.iter_profiles()}
        scope_selector = sel.SelectSelector(sel.SelectSelectorConfig(options=PROFILE_SCOPE_SELECTOR_OPTIONS))
        schema = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required(CONF_PROFILE_SCOPE, default=PROFILE_SCOPE_DEFAULT): scope_selector,
                vol.Optional("copy_from"): vol.In(profiles) if profiles else str,
            }
        )
        return self.async_show_form(step_id="add_profile", data_schema=schema)

    async def async_step_manage_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        profiles = self._profiles()
        if not profiles:
            return self.async_abort(reason="no_profiles")

        if user_input is None:
            options = {pid: data.get("name", pid) for pid, data in profiles.items()}
            actions = {
                "edit_general": "Edit details",
                "edit_sensors": "Edit sensors",
                "edit_thresholds": "Edit targets",
                "delete": "Delete profile",
            }
            return self.async_show_form(
                step_id="manage_profiles",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile_id"): vol.In(options),
                        vol.Required("action", default="edit_general"): vol.In(actions),
                    }
                ),
            )

        self._pid = user_input["profile_id"]
        action = user_input["action"]
        if action == "edit_general":
            return await self.async_step_manage_profile_general()
        if action == "edit_sensors":
            return await self.async_step_manage_profile_sensors()
        if action == "edit_thresholds":
            return await self.async_step_manage_profile_thresholds()
        if action == "delete":
            return await self.async_step_manage_profile_delete()
        return self.async_abort(reason="unknown_profile")

    async def async_step_manage_profile_general(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        registry = await self._async_get_registry()
        profiles = self._profiles()
        if not self._pid or self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile = profiles[self._pid]
        general = profile.get("general", {}) if isinstance(profile.get("general"), Mapping) else {}
        defaults = {
            "name": profile.get("name", self._pid),
            "plant_type": general.get(CONF_PLANT_TYPE, profile.get("species_display", "")),
            CONF_PROFILE_SCOPE: general.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT),
            "species_display": profile.get("species_display", general.get("plant_type", "")),
        }
        scope_selector = sel.SelectSelector(sel.SelectSelectorConfig(options=PROFILE_SCOPE_SELECTOR_OPTIONS))
        schema = vol.Schema(
            {
                vol.Required("name", default=defaults["name"]): str,
                vol.Optional("plant_type", default=defaults["plant_type"]): str,
                vol.Required(CONF_PROFILE_SCOPE, default=defaults[CONF_PROFILE_SCOPE]): scope_selector,
                vol.Optional("species_display", default=defaults["species_display"]): str,
            }
        )

        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"profile": defaults["name"]}
        if user_input is not None:
            new_name = user_input["name"].strip()
            if not new_name:
                errors["name"] = "required"
            if not errors:
                try:
                    await registry.async_update_profile_general(
                        self._pid,
                        name=new_name,
                        plant_type=user_input.get("plant_type", "").strip() or None,
                        scope=user_input.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT),
                        species_display=user_input.get("species_display", "").strip() or None,
                    )
                except ValueError:
                    errors["base"] = "update_failed"
                else:
                    return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_general",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_manage_profile_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        registry = await self._async_get_registry()
        profiles = self._profiles()
        if not self._pid or self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile = profiles[self._pid]
        general = profile.get("general", {}) if isinstance(profile.get("general"), Mapping) else {}
        existing = general.get("sensors", {}) if isinstance(general.get("sensors"), Mapping) else {}
        description_placeholders = {
            "profile": profile.get("name") or self._pid,
            "error": "",
        }

        schema_fields: dict[Any, Any] = {}
        for measurement, selector in PROFILE_SENSOR_FIELDS.items():
            default_value = existing.get(measurement, "") if isinstance(existing, Mapping) else ""
            schema_fields[vol.Optional(measurement, default=default_value)] = vol.Any(selector, str)
        schema = vol.Schema(schema_fields)

        errors: dict[str, str] = {}
        if user_input is not None:
            sensors: dict[str, str] = {}
            for measurement in PROFILE_SENSOR_FIELDS:
                raw = user_input.get(measurement)
                if isinstance(raw, str) and raw.strip():
                    sensors[measurement] = raw.strip()
            try:
                await registry.async_set_profile_sensors(self._pid, sensors)
            except ValueError as err:
                errors["base"] = "sensor_validation_failed"
                description_placeholders["error"] = str(err)
            else:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_sensors",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_manage_profile_thresholds(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        registry = await self._async_get_registry()
        profiles = self._profiles()
        if not self._pid or self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile = profiles[self._pid]
        thresholds_payload = (
            profile.get("thresholds") if isinstance(profile.get("thresholds"), Mapping) else {}
        )
        resolved_payload = (
            profile.get("resolved_targets")
            if isinstance(profile.get("resolved_targets"), Mapping)
            else {}
        )

        def _resolve_default(key: str) -> str:
            if isinstance(thresholds_payload, Mapping):
                value = thresholds_payload.get(key)
                if isinstance(value, (int, float)):
                    return str(value)
                if isinstance(value, str) and value.strip():
                    return value
            if isinstance(resolved_payload, Mapping):
                value = resolved_payload.get(key)
                if isinstance(value, Mapping):
                    raw = value.get("value")
                    if isinstance(raw, (int, float)):
                        return str(raw)
                    if isinstance(raw, str) and raw.strip():
                        return raw
            return ""

        schema_fields: dict[Any, Any] = {}
        for key in MANUAL_THRESHOLD_FIELDS:
            schema_fields[vol.Optional(key, default=_resolve_default(key))] = vol.Any(str, int, float)
        schema = vol.Schema(schema_fields)

        errors: dict[str, str] = {}
        placeholders = {"profile": profile.get("name") or self._pid, "issue_detail": ""}

        if user_input is not None:
            cleaned: dict[str, float] = {}
            removed: set[str] = set()
            candidate = (
                dict(thresholds_payload)
                if isinstance(thresholds_payload, Mapping)
                else {}
            )

            for key in MANUAL_THRESHOLD_FIELDS:
                raw = user_input.get(key)
                if raw in (None, "", []):
                    if key in candidate:
                        candidate.pop(key, None)
                        removed.add(key)
                    continue
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    errors[key] = "invalid_float"
                    continue
                cleaned[key] = value
                candidate[key] = value

            if errors:
                return self.async_show_form(
                    step_id="manage_profile_thresholds",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders=placeholders,
                )

            violations = evaluate_threshold_bounds(candidate)
            if violations:
                placeholders["issue_detail"] = "\n".join(issue.message() for issue in violations[:3])
                for issue in violations:
                    if issue.key in MANUAL_THRESHOLD_FIELDS:
                        errors[issue.key] = "threshold_field_error"
                errors["base"] = "threshold_out_of_bounds"
                return self.async_show_form(
                    step_id="manage_profile_thresholds",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders=placeholders,
                )

            target_keys = set(cleaned.keys()) | removed
            try:
                await registry.async_update_profile_thresholds(
                    self._pid,
                    cleaned,
                    allowed_keys=target_keys,
                    removed_keys=removed,
                )
            except ValueError as err:
                errors["base"] = "update_failed"
                placeholders["issue_detail"] = str(err)
            else:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_thresholds",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_manage_profile_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        registry = await self._async_get_registry()
        primary_id = get_primary_profile_id(self._entry)
        if not self._pid:
            return self.async_abort(reason="unknown_profile")
        if self._pid == primary_id:
            return self.async_abort(reason="cannot_delete_primary")

        profiles = self._profiles()
        if self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile_name = profiles[self._pid].get("name") or self._pid
        schema = vol.Schema({vol.Required("confirm", default=False): bool})
        placeholders = {"profile": profile_name}

        if user_input is not None:
            if user_input.get("confirm"):
                try:
                    await registry.async_delete_profile(self._pid)
                except ValueError:
                    return self.async_abort(reason="unknown_profile")
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_delete",
            data_schema=schema,
            description_placeholders=placeholders,
        )

    async def async_step_configure_ai(self, user_input: dict[str, Any] | None = None):
        opts = dict(self._entry.options)
        defaults = {
            CONF_API_KEY: opts.get(CONF_API_KEY, self._entry.data.get(CONF_API_KEY, "")),
            CONF_MODEL: opts.get(CONF_MODEL, self._entry.data.get(CONF_MODEL, DEFAULT_MODEL)),
            CONF_BASE_URL: opts.get(CONF_BASE_URL, self._entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)),
            CONF_UPDATE_INTERVAL: opts.get(
                CONF_UPDATE_INTERVAL,
                self._entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
            ),
        }

        schema = vol.Schema(
            {
                vol.Optional(CONF_API_KEY, default=defaults[CONF_API_KEY]): sel.TextSelector(
                    sel.TextSelectorConfig(type="password")
                ),
                vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
                vol.Optional(CONF_BASE_URL, default=defaults[CONF_BASE_URL]): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): vol.All(
                    int, vol.Range(min=1, max=60)
                ),
            }
        )

        if user_input is not None:
            new_options = {**opts}
            for key, value in user_input.items():
                if value in (None, ""):
                    new_options.pop(key, None)
                else:
                    new_options[key] = value
            return self.async_create_entry(title="AI settings updated", data=new_options)

        return self.async_show_form(step_id="configure_ai", data_schema=schema)

    async def async_step_attach_sensors(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        from .profile_registry import ProfileRegistry

        registry: ProfileRegistry = self.hass.data[DOMAIN]["registry"]
        pid = self._new_profile_id
        errors: dict[str, str] = {}
        if user_input is not None and pid:
            sensors: dict[str, str] = {}
            for role in ("temperature", "humidity", "illuminance", "moisture"):
                if ent := user_input.get(role):
                    sensors[role] = ent
            if sensors:
                validation = validate_sensor_links(self.hass, sensors)
                for issue in validation.errors:
                    errors[issue.role] = issue.issue
                if validation.warnings:
                    self._notify_sensor_warnings(validation.warnings)
                if not errors:
                    await registry.async_link_sensors(pid, sensors)
                    return self.async_create_entry(title="", data={})
        schema = vol.Schema(
            {
                vol.Optional("temperature"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])
                ),
                vol.Optional("humidity"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["humidity"])
                ),
                vol.Optional("illuminance"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["illuminance"])
                ),
                vol.Optional("moisture"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])
                ),
            }
        )
        return self.async_show_form(step_id="attach_sensors", data_schema=schema, errors=errors)

    async def async_step_calibration(self, user_input=None):
        schema = vol.Schema(
            {
                vol.Required("lux_entity_id"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain="sensor", device_class="illuminance")
                ),
                vol.Optional("ppfd_entity_id"): sel.EntitySelector(sel.EntitySelectorConfig(domain="sensor")),
                vol.Optional("model", default="linear"): vol.In(["linear", "quadratic", "power"]),
                vol.Optional("averaging_seconds", default=3): int,
                vol.Optional("notes"): str,
            }
        )
        if user_input is not None:
            res = await self.hass.services.async_call(
                DOMAIN,
                "start_calibration",
                user_input,
                blocking=True,
                return_response=True,
            )
            self._cal_session = res.get("session_id")
            return await self.async_step_calibration_collect()
        return self.async_show_form(step_id="calibration", data_schema=schema)

    async def async_step_calibration_collect(self, user_input=None):
        schema = vol.Schema(
            {
                vol.Required("action", default="add"): vol.In(
                    [
                        "add",
                        "finish",
                        "abort",
                    ]
                ),
                vol.Optional("ppfd_value"): float,
            }
        )
        if user_input is not None and self._cal_session:
            action = user_input["action"]
            if action == "add":
                data = {"session_id": self._cal_session}
                if user_input.get("ppfd_value") is not None:
                    data["ppfd_value"] = user_input["ppfd_value"]
                await self.hass.services.async_call(DOMAIN, "add_calibration_point", data, blocking=True)
                return await self.async_step_calibration_collect()
            if action == "finish":
                await self.hass.services.async_call(
                    DOMAIN,
                    "finish_calibration",
                    {"session_id": self._cal_session},
                    blocking=True,
                )
                return self.async_create_entry(title="calibration", data={})
            if action == "abort":
                await self.hass.services.async_call(
                    DOMAIN,
                    "abort_calibration",
                    {"session_id": self._cal_session},
                    blocking=True,
                )
                return self.async_create_entry(title="calibration", data={})
        return self.async_show_form(step_id="calibration_collect", data_schema=schema)

    # --- Per-variable source editing ---

    async def async_step_profile(self, user_input=None):
        profiles = self._profiles()
        if user_input is not None:
            self._pid = user_input["profile_id"]
            return await self.async_step_action()
        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema(
                {vol.Required("profile_id"): vol.In({pid: p["name"] for pid, p in profiles.items()})}
            ),
        )

    async def async_step_action(self, user_input=None):
        actions = {"edit": "Edit variable", "generate": "Generate profile"}
        if user_input is not None:
            act = user_input["action"]
            if act == "edit":
                return await self.async_step_pick_variable()
            return await self.async_step_generate()
        return self.async_show_form(
            step_id="action",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)}),
        )

    async def async_step_pick_variable(self, user_input=None):
        from .const import VARIABLE_SPECS

        if user_input is not None:
            self._var = user_input["variable"]
            return await self.async_step_pick_source()
        return self.async_show_form(
            step_id="pick_variable",
            data_schema=vol.Schema({vol.Required("variable"): vol.In([k for k, *_ in VARIABLE_SPECS])}),
        )

    async def async_step_pick_source(self, user_input=None):
        from .const import SOURCES

        if user_input is not None:
            self._mode = user_input["mode"]
            if self._mode == "manual":
                return await self.async_step_src_manual()
            if self._mode == "clone":
                return await self.async_step_src_clone()
            if self._mode == "opb":
                return await self.async_step_src_opb()
            if self._mode == "ai":
                return await self.async_step_src_ai()
        return self.async_show_form(
            step_id="pick_source",
            data_schema=vol.Schema({vol.Required("mode"): vol.In(SOURCES)}),
        )

    async def async_step_src_manual(self, user_input=None):
        if user_input is not None:
            self._set_source({"mode": "manual", "value": float(user_input["value"])})
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_manual",
            data_schema=vol.Schema({vol.Required("value"): float}),
        )

    async def async_step_src_clone(self, user_input=None):
        profs = {pid: p["name"] for pid, p in self._profiles().items() if pid != self._pid}
        if user_input is not None:
            self._set_source({"mode": "clone", "copy_from": user_input["copy_from"]})
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_clone",
            data_schema=vol.Schema({vol.Required("copy_from"): vol.In(profs)}),
        )

    async def async_step_src_opb(self, user_input=None):
        if user_input is not None:
            self._set_source(
                {
                    "mode": "opb",
                    "opb": {"species": user_input["species"], "field": user_input["field"]},
                }
            )
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_opb",
            data_schema=vol.Schema({vol.Required("species"): str, vol.Required("field"): str}),
        )

    async def async_step_src_ai(self, user_input=None):
        if user_input is not None:
            self._set_source(
                {
                    "mode": "ai",
                    "ai": {
                        "provider": user_input.get("provider", "openai"),
                        "model": user_input.get("model", "gpt-4o-mini"),
                        "ttl_hours": int(user_input.get("ttl_hours", 720)),
                    },
                }
            )
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_ai",
            data_schema=vol.Schema(
                {
                    vol.Optional("provider", default="openai"): str,
                    vol.Optional("model", default="gpt-4o-mini"): str,
                    vol.Optional("ttl_hours", default=720): int,
                }
            ),
        )

    async def async_step_generate(self, user_input=None):
        if user_input is not None:
            mode = user_input["mode"]
            if mode == "clone":
                return await self.async_step_generate_clone()
            self._generate_all(mode)
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="generate",
            data_schema=vol.Schema({vol.Required("mode"): vol.In(["clone", "opb", "ai"])}),
        )

    async def async_step_generate_clone(self, user_input=None):
        profs = {pid: p["name"] for pid, p in self._profiles().items() if pid != self._pid}
        if user_input is not None:
            self._generate_all("clone", user_input["copy_from"])
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="generate_clone",
            data_schema=vol.Schema({vol.Required("copy_from"): vol.In(profs)}),
        )

    def _profiles(self):
        profiles: dict[str, dict[str, Any]] = {}
        for pid, payload in (self._entry.options.get(CONF_PROFILES, {}) or {}).items():
            copy = dict(payload)
            ensure_sections(copy, plant_id=pid, display_name=copy.get("name") or pid)
            profiles[pid] = copy
        return profiles

    def _set_source(self, src: dict):
        opts = dict(self._entry.options)
        prof = dict(opts.get(CONF_PROFILES, {}).get(self._pid, {}))
        ensure_sections(prof, plant_id=self._pid, display_name=prof.get("name") or self._pid)
        sources = dict(prof.get("sources", {}))
        sources[self._var] = src
        prof["sources"] = sources
        prof["needs_resolution"] = True
        allp = dict(opts.get(CONF_PROFILES, {}))
        allp[self._pid] = prof
        opts[CONF_PROFILES] = allp
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

    def _generate_all(self, mode: str, source_profile_id: str | None = None):
        from .const import VARIABLE_SPECS

        opts = dict(self._entry.options)
        prof = dict(opts.get(CONF_PROFILES, {}).get(self._pid, {}))
        library_section, local_section = ensure_sections(
            prof,
            plant_id=self._pid,
            display_name=prof.get("name") or self._pid,
        )
        sources = dict(prof.get("sources", {}))
        slug = determine_species_slug(
            library=library_section,
            local=local_section,
            raw=prof.get("species"),
        )
        if mode == "clone":
            if not source_profile_id:
                raise ValueError("source_profile_id required for clone")
            other = dict(opts.get(CONF_PROFILES, {}).get(source_profile_id, {}))
            ensure_sections(
                other,
                plant_id=source_profile_id,
                display_name=other.get("name") or source_profile_id,
            )
            prof["thresholds"] = dict(other.get("thresholds", {}))
            if isinstance(other.get("resolved_targets"), dict):
                prof["resolved_targets"] = deepcopy(other.get("resolved_targets"))
            else:
                prof.pop("resolved_targets", None)
            if isinstance(other.get("variables"), dict):
                prof["variables"] = deepcopy(other.get("variables"))
            else:
                prof.pop("variables", None)
            sync_thresholds(prof, default_source="clone")
            for key, *_ in VARIABLE_SPECS:
                sources[key] = {"mode": "clone", "copy_from": source_profile_id}
        else:
            for key, *_ in VARIABLE_SPECS:
                if mode == "opb":
                    sources[key] = {"mode": "opb", "opb": {"species": slug, "field": key}}
                else:
                    sources[key] = {
                        "mode": "ai",
                        "ai": {
                            "provider": "openai",
                            "model": "gpt-4o-mini",
                            "ttl_hours": 720,
                        },
                    }
        prof["sources"] = sources
        prof["needs_resolution"] = True
        allp = dict(opts.get(CONF_PROFILES, {}))
        allp[self._pid] = prof
        opts[CONF_PROFILES] = allp
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

    def _infer_nutrient_schedule_plant_type(self, profile: Mapping[str, Any]) -> str | None:
        """Return the best available species or plant-type identifier for a profile."""

        def _as_str(value: Any) -> str | None:
            if isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    return candidate
            return None

        containers: list[Mapping[str, Any]] = []
        local_section = profile.get("local")
        if isinstance(local_section, Mapping):
            containers.append(local_section)
            general = local_section.get("general")
            if isinstance(general, Mapping):
                containers.append(general)
        general_section = profile.get("general")
        if isinstance(general_section, Mapping):
            containers.append(general_section)

        sections = profile.get("sections")
        if isinstance(sections, Mapping):
            local = sections.get("local")
            if isinstance(local, Mapping):
                general = local.get("general")
                if isinstance(general, Mapping):
                    containers.append(general)

        for container in containers:
            for field in ("plant_type", "species", "slug"):
                candidate = _as_str(container.get(field))
                if candidate:
                    return candidate

        for field in ("species", "plant_type", "species_display"):
            candidate = _as_str(profile.get(field))
            if candidate:
                return candidate

        library = profile.get("library")
        if isinstance(library, Mapping):
            for key in ("identity", "taxonomy"):
                payload = library.get(key)
                if not isinstance(payload, Mapping):
                    continue
                for field in ("plant_type", "species", "binomial", "slug", "name"):
                    candidate = _as_str(payload.get(field))
                    if candidate:
                        return candidate

        if isinstance(sections, Mapping):
            library_section = sections.get("library")
            if isinstance(library_section, Mapping):
                for key in ("identity", "taxonomy"):
                    payload = library_section.get(key)
                    if not isinstance(payload, Mapping):
                        continue
                    for field in ("plant_type", "species", "binomial", "slug", "name"):
                        candidate = _as_str(payload.get(field))
                        if candidate:
                            return candidate

        return None

    def _extract_nutrient_schedule(self, profile: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Extract the stored nutrient schedule for ``profile`` if one exists."""

        def _schedule_from(container: Mapping[str, Any] | None) -> list[dict[str, Any]] | None:
            if not isinstance(container, Mapping):
                return None
            schedule = container.get("nutrient_schedule")
            if isinstance(schedule, list):
                return [dict(item) for item in schedule if isinstance(item, Mapping)]
            nutrients = container.get("nutrients")
            if isinstance(nutrients, Mapping):
                schedule = nutrients.get("schedule")
                if isinstance(schedule, list):
                    return [dict(item) for item in schedule if isinstance(item, Mapping)]
            metadata = container.get("metadata")
            if isinstance(metadata, Mapping):
                schedule = metadata.get("nutrient_schedule")
                if isinstance(schedule, list):
                    return [dict(item) for item in schedule if isinstance(item, Mapping)]
            return None

        containers: list[Mapping[str, Any] | None] = [
            profile.get("local"),
            profile.get("general"),
        ]
        local_section = profile.get("local")
        if isinstance(local_section, Mapping):
            containers.append(local_section.get("general"))
        sections = profile.get("sections")
        if isinstance(sections, Mapping):
            local = sections.get("local")
            if isinstance(local, Mapping):
                containers.append(local.get("general"))
        containers.append(profile)

        for container in containers:
            schedule = _schedule_from(container)
            if schedule:
                return schedule
        return []

    def _generate_schedule_for_profile(self, profile: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Generate a nutrient schedule payload for ``profile`` using heuristics."""

        plant_type = self._infer_nutrient_schedule_plant_type(profile)
        if not plant_type:
            raise ValueError("missing_plant_type")

        stages = generate_nutrient_schedule(plant_type)
        if not stages:
            raise ValueError("no_schedule")

        schedule: list[dict[str, Any]] = []
        current_day = 1
        for index, stage in enumerate(stages, start=1):
            stage_name = getattr(stage, "stage", None) or getattr(stage, "name", None) or f"stage_{index}"
            try:
                duration = int(getattr(stage, "duration_days", 0) or 0)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                duration = 0
            totals_raw = getattr(stage, "totals", {})
            if not isinstance(totals_raw, Mapping):
                totals_raw = {}
            totals: dict[str, float] = {}
            for nutrient, amount in totals_raw.items():
                if nutrient is None:
                    continue
                try:
                    totals[str(nutrient)] = float(amount)
                except (TypeError, ValueError):
                    continue

            entry: dict[str, Any] = {
                "stage": str(stage_name),
                "duration_days": max(duration, 0),
                "totals_mg": totals,
                "source": "auto_generate",
            }
            if entry["duration_days"] > 0:
                entry["start_day"] = current_day
                entry["end_day"] = current_day + entry["duration_days"] - 1
                entry["daily_mg"] = {
                    nutrient: round(amount / entry["duration_days"], 4) for nutrient, amount in totals.items()
                }
                current_day = entry["end_day"] + 1
            else:
                entry["start_day"] = current_day
                entry["end_day"] = current_day
                if totals:
                    entry["daily_mg"] = dict(totals)
            schedule.append(entry)

        return schedule

    def _coerce_schedule_row(self, item: Any) -> dict[str, Any]:
        """Normalise a raw nutrient schedule entry."""

        if not isinstance(item, Mapping):
            raise ValueError("schedule_row_not_mapping")

        def _as_str(value: Any) -> str | None:
            if isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    return candidate
            return None

        stage = _as_str(item.get("stage") or item.get("name") or item.get("phase"))
        if not stage:
            raise ValueError("missing_stage")

        duration_raw = item.get("duration_days") or item.get("duration") or item.get("days") or item.get("length_days")
        try:
            duration = int(float(duration_raw)) if duration_raw is not None else None
        except (TypeError, ValueError) as err:  # pragma: no cover - defensive
            raise ValueError("invalid_duration") from err
        if duration is None or duration < 0:
            raise ValueError("invalid_duration")

        totals: dict[str, float] = {}
        totals_raw = item.get("totals_mg") or item.get("totals") or item.get("nutrients") or item.get("targets")
        if isinstance(totals_raw, Mapping):
            for nutrient, amount in totals_raw.items():
                name = _as_str(nutrient) or str(nutrient)
                try:
                    totals[name] = float(amount)
                except (TypeError, ValueError):
                    continue
        elif isinstance(totals_raw, list):
            for entry in totals_raw:
                if not isinstance(entry, Mapping):
                    continue
                nutrient = _as_str(entry.get("nutrient") or entry.get("id") or entry.get("name"))
                if not nutrient:
                    continue
                try:
                    totals[nutrient] = float(entry.get("value") or entry.get("amount"))
                except (TypeError, ValueError):
                    continue

        def _as_int(value: Any) -> int | None:
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        start_day = _as_int(item.get("start_day") or item.get("day_start") or item.get("start"))
        end_day = _as_int(item.get("end_day") or item.get("day_end") or item.get("end"))

        result: dict[str, Any] = {
            "stage": stage,
            "duration_days": duration,
            "totals_mg": totals,
        }
        if start_day is not None:
            result["start_day"] = start_day
        if end_day is None and start_day is not None and duration > 0:
            end_day = start_day + duration - 1
        if end_day is not None:
            result["end_day"] = end_day
        if totals:
            if duration > 0:
                result["daily_mg"] = {nutrient: round(amount / duration, 4) for nutrient, amount in totals.items()}
            else:
                result["daily_mg"] = dict(totals)

        notes = _as_str(item.get("notes") or item.get("description"))
        if notes:
            result["notes"] = notes
        source = _as_str(item.get("source") or item.get("mode"))
        if source:
            result["source"] = source

        return result

    def _apply_nutrient_schedule(self, profile_id: str | None, schedule: list[dict[str, Any]]) -> None:
        """Persist ``schedule`` to the config entry options for ``profile_id``."""

        if not profile_id:
            return

        safe_schedule = json.loads(json.dumps(schedule, ensure_ascii=False))
        opts = dict(self._entry.options)
        profiles = dict(opts.get(CONF_PROFILES, {}))
        profile = dict(profiles.get(profile_id, {}))

        ensure_sections(profile, plant_id=profile_id, display_name=profile.get("name") or profile_id)

        local = profile.get("local")
        local_dict = dict(local) if isinstance(local, Mapping) else {}
        general_local = local_dict.get("general")
        general_local_dict = dict(general_local) if isinstance(general_local, Mapping) else {}
        general_local_dict["nutrient_schedule"] = safe_schedule
        local_dict["general"] = general_local_dict
        profile["local"] = local_dict

        general = profile.get("general")
        general_dict = dict(general) if isinstance(general, Mapping) else {}
        general_dict["nutrient_schedule"] = safe_schedule
        profile["general"] = general_dict

        ensure_sections(profile, plant_id=profile_id, display_name=profile.get("name") or profile_id)

        profiles[profile_id] = profile
        opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

    async def async_step_apply(self, user_input=None):
        if user_input is not None:
            if user_input.get("resolve_now"):
                from .resolver import PreferenceResolver

                await PreferenceResolver(self.hass).resolve_profile(self._entry, self._pid)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="apply",
            data_schema=vol.Schema({vol.Optional("resolve_now", default=True): bool}),
        )


# Backwards compatibility for older imports
class HorticultureAssistantConfigFlow(ConfigFlow):
    """Retain legacy class name for tests and external references."""

    pass
