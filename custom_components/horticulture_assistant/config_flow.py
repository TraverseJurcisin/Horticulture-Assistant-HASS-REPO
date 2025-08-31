from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from aiohttp import ClientError
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector as sel

from .api import ChatApi
from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CO2_SENSOR,
    CONF_EC_SENSOR,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_MOISTURE_SENSOR,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PLANT_TYPE,
    CONF_TEMPERATURE_SENSOR,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_KEEP_STALE,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
)
from .opb_client import OpenPlantbookClient
from .utils import profile_generator
from .utils.json_io import load_json, save_json
from .utils.plant_registry import register_plant

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): str,
        vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
        vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_MINUTES): vol.All(int, vol.Range(min=1)),
    }
)

PROFILE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLANT_NAME): cv.string,
        vol.Optional(CONF_PLANT_TYPE): cv.string,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc,call-arg]
    VERSION = 2

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
        errors = {}
        if user_input is not None:
            api = ChatApi(
                self.hass,
                user_input.get(CONF_API_KEY, ""),
                user_input.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                user_input.get(CONF_MODEL, DEFAULT_MODEL),
            )
            try:
                await api.validate_api_key()
            except (TimeoutError, ClientError) as err:
                errors["base"] = "cannot_connect"
                _LOGGER.error("API key validation failed: %s", err)
            except Exception as err:  # pragma: no cover - unexpected
                errors["base"] = "cannot_connect"
                _LOGGER.exception("Unexpected error validating API key: %s", err)
            if not errors:
                self._config = user_input
                return await self.async_step_profile()
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

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
        if self._config is None or self._profile is None:
            return self.async_abort(reason="unknown")
        if user_input is not None:
            method = user_input["method"]
            if method == "openplantbook":
                return await self.async_step_opb_credentials()
            return await self.async_step_thresholds()
        schema = vol.Schema(
            {
                vol.Required("method", default="manual"): sel.SelectSelector(
                    sel.SelectSelectorConfig(
                        options=[
                            {"value": "openplantbook", "label": "From OpenPlantbook"},
                            {"value": "manual", "label": "Manual entry"},
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
        if self._config is None or self._profile is None:
            return self.async_abort(reason="unknown")

        defaults = self._thresholds
        schema = vol.Schema(
            {
                vol.Optional("temperature_min", default=defaults.get("temperature_min")): vol.Coerce(float),
                vol.Optional("temperature_max", default=defaults.get("temperature_max")): vol.Coerce(float),
                vol.Optional("humidity_min", default=defaults.get("humidity_min")): vol.Coerce(float),
                vol.Optional("humidity_max", default=defaults.get("humidity_max")): vol.Coerce(float),
                vol.Optional("illuminance_min", default=defaults.get("illuminance_min")): vol.Coerce(float),
                vol.Optional("illuminance_max", default=defaults.get("illuminance_max")): vol.Coerce(float),
                vol.Optional("conductivity_min", default=defaults.get("conductivity_min")): vol.Coerce(float),
                vol.Optional("conductivity_max", default=defaults.get("conductivity_max")): vol.Coerce(float),
            }
        )

        if user_input is not None:
            self._thresholds = {k: v for k, v in user_input.items() if v is not None}
            return await self.async_step_sensors()

        return self.async_show_form(step_id="thresholds", data_schema=schema)

    async def async_step_sensors(self, user_input=None):
        if self._config is None or self._profile is None:
            return self.async_abort(reason="unknown")

        schema = vol.Schema(
            {
                vol.Optional(CONF_MOISTURE_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])),
                    str,
                ),
                vol.Optional(CONF_TEMPERATURE_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])),
                    str,
                ),
                vol.Optional(CONF_EC_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"])),
                    str,
                ),
                vol.Optional(CONF_CO2_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["carbon_dioxide"])),
                    str,
                ),
            }
        )

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
                return self.async_show_form(step_id="sensors", data_schema=schema, errors=errors)
            sensor_map = {}
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
            data = {**self._config, **self._profile}
            options = dict(user_input)
            options["sensors"] = mapped
            options["thresholds"] = self._thresholds
            if self._species_display:
                options["species_display"] = self._species_display
            if self._species_pid:
                options["species_pid"] = self._species_pid
            if self._image_url:
                options["image_url"] = self._image_url
            if self._opb_credentials:
                options["opb_credentials"] = self._opb_credentials
            return self.async_create_entry(title=self._profile[CONF_PLANT_NAME], data=data, options=options)

        return self.async_show_form(step_id="sensors", data_schema=schema)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self._entry = entry
        self._pid: str | None = None
        self._var: str | None = None
        self._mode: str | None = None
        self._cal_session: str | None = None
        self._new_profile_id: str | None = None

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["basic", "add_profile"],
        )

    async def async_step_basic(self, user_input=None):
        defaults = {
            CONF_MODEL: self._entry.data.get(CONF_MODEL, DEFAULT_MODEL),
            CONF_BASE_URL: self._entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            CONF_UPDATE_INTERVAL: self._entry.options.get(
                CONF_UPDATE_INTERVAL,
                self._entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
            ),
            CONF_KEEP_STALE: self._entry.options.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
            "species_display": self._entry.options.get("species_display", self._entry.data.get(CONF_PLANT_TYPE, "")),
            "opb_auto_download_images": self._entry.options.get("opb_auto_download_images", True),
            "opb_download_dir": self._entry.options.get(
                "opb_download_dir",
                self.hass.config.path("www/images/plants"),
            ),
            "opb_location_share": self._entry.options.get("opb_location_share", "off"),
            "opb_enable_upload": self._entry.options.get("opb_enable_upload", False),
        }

        schema = vol.Schema(
            {
                vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
                vol.Optional(CONF_BASE_URL, default=defaults[CONF_BASE_URL]): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): int,
                vol.Optional(CONF_MOISTURE_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])),
                    str,
                ),
                vol.Optional(CONF_TEMPERATURE_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])),
                    str,
                ),
                vol.Optional(CONF_EC_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"])),
                    str,
                ),
                vol.Optional(CONF_CO2_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["carbon_dioxide"])),
                    str,
                ),
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
        )

        errors = {}
        if user_input is not None:
            if user_input.get(CONF_UPDATE_INTERVAL, 1) < 1:
                errors[CONF_UPDATE_INTERVAL] = "invalid_interval"
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
                return self.async_show_form(step_id="basic", data_schema=schema, errors=errors)
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

        return self.async_show_form(step_id="basic", data_schema=schema)

    async def async_step_add_profile(self, user_input=None):
        from .profile_registry import ProfileRegistry

        registry: ProfileRegistry = self.hass.data[DOMAIN]["profile_registry"]
        if user_input is not None:
            pid = await registry.async_add_profile(user_input["name"], user_input.get("copy_from"))
            self._new_profile_id = pid
            return await self.async_step_attach_sensors()
        profiles = {p.plant_id: p.display_name for p in registry.iter_profiles()}
        schema = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Optional("copy_from"): vol.In(profiles) if profiles else str,
            }
        )
        return self.async_show_form(step_id="add_profile", data_schema=schema)

    async def async_step_attach_sensors(self, user_input=None):
        from .profile_registry import ProfileRegistry

        registry: ProfileRegistry = self.hass.data[DOMAIN]["profile_registry"]
        pid = self._new_profile_id
        if user_input is not None and pid:
            sensors: dict[str, str] = {}
            for role in ("temperature", "humidity", "illuminance", "moisture"):
                if ent := user_input.get(role):
                    sensors[role] = ent
            if sensors:
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
        return self.async_show_form(step_id="attach_sensors", data_schema=schema)

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
        return dict(self._entry.options.get("profiles", {}))

    def _set_source(self, src: dict):
        opts = dict(self._entry.options)
        prof = dict(opts.get("profiles", {}).get(self._pid, {}))
        sources = dict(prof.get("sources", {}))
        sources[self._var] = src
        prof["sources"] = sources
        prof["needs_resolution"] = True
        allp = dict(opts.get("profiles", {}))
        allp[self._pid] = prof
        opts["profiles"] = allp
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

    def _generate_all(self, mode: str, source_profile_id: str | None = None):
        from .const import VARIABLE_SPECS

        opts = dict(self._entry.options)
        prof = dict(opts.get("profiles", {}).get(self._pid, {}))
        sources = dict(prof.get("sources", {}))
        species = prof.get("species")
        slug = species.get("slug") if isinstance(species, dict) else species
        if mode == "clone":
            if not source_profile_id:
                raise ValueError("source_profile_id required for clone")
            other = opts.get("profiles", {}).get(source_profile_id, {})
            prof["thresholds"] = dict(other.get("thresholds", {}))
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
        allp = dict(opts.get("profiles", {}))
        allp[self._pid] = prof
        opts["profiles"] = allp
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
