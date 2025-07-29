"""Config flow for Horticulture Assistant integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    TextSelector,
    EntitySelector,
)
from uuid import uuid4

from .utils.profile_generator import generate_profile

from .const import (
    DOMAIN,
    CONF_ENABLE_AUTO_APPROVE,
    CONF_DEFAULT_THRESHOLD_MODE,
    CONF_USE_OPENAI,
    CONF_OPENAI_API_KEY,
    CONF_OPENAI_MODEL,
    THRESHOLD_MODE_MANUAL,
    THRESHOLD_MODE_PROFILE,
)
from .utils import global_config

class HorticultureAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Horticulture Assistant."""

    VERSION = 3

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_init(self, user_input: str | None = None) -> FlowResult:
        """Show menu to add or manage entries from the integration page."""
        if user_input is None:
            return self.async_show_menu(
                step_id="init",
                menu_options=["add_entry", "manage_entries", "settings"],
            )

        if user_input == "add_entry":
            return await self.async_step_user()

        if user_input == "manage_entries":
            entries = self.hass.config_entries.async_entries(DOMAIN)
            if not entries:
                return self.async_abort(reason="no_entries")

            options = {
                entry.entry_id: entry.data.get("plant_name", entry.entry_id)
                for entry in entries
            }
            self._entry_map = options
            return self.async_show_form(
                step_id="select_entry",
                data_schema=vol.Schema({vol.Required("entry_id"): vol.In(options)}),
            )
        if user_input == "settings":
            return await self.async_step_settings()
        return self.async_abort(reason="invalid_menu_selection")

    async def async_step_select_entry(self, user_input: dict) -> FlowResult:
        """Abort with placeholder when an entry is chosen."""
        entry_id = user_input.get("entry_id")
        return self.async_abort(
            reason="existing_entry",
            description_placeholders={"entry_id": entry_id},
        )

    async def async_step_settings(
        self, user_input: dict | None = None
    ) -> FlowResult:
        """Configure global integration options."""
        cfg = global_config.load_config(self.hass)
        if user_input is not None:
            cfg.update(user_input)
            global_config.save_config(cfg, self.hass)
            return await self.async_step_init()

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USE_OPENAI, default=cfg.get(CONF_USE_OPENAI, False)
                ): BooleanSelector(),
                vol.Optional(
                    CONF_OPENAI_MODEL, default=cfg.get(CONF_OPENAI_MODEL, "gpt-4o")
                ): TextSelector(),
                vol.Optional(
                    CONF_OPENAI_API_KEY, default=cfg.get(CONF_OPENAI_API_KEY, "")
                ): TextSelector(),
                vol.Optional(
                    CONF_DEFAULT_THRESHOLD_MODE,
                    default=cfg.get(
                        CONF_DEFAULT_THRESHOLD_MODE, THRESHOLD_MODE_PROFILE
                    ),
                ): vol.In([THRESHOLD_MODE_PROFILE, THRESHOLD_MODE_MANUAL]),
            }
        )

        return self.async_show_form(step_id="settings", data_schema=data_schema)

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Collect minimal information and create the entry."""
        data_schema = vol.Schema({
            vol.Required("plant_name"): TextSelector(),
            vol.Optional("zone_id"): TextSelector(),
        })

        if user_input is not None:
            self._data.update(user_input)
            plant_id = generate_profile(self._data, self.hass)
            if plant_id:
                self._data["profile_generated"] = True
                self._data["plant_id"] = plant_id
            else:
                self._data["profile_generated"] = False
                self._data["plant_id"] = f"pending_{uuid4().hex}"
            set_uid = getattr(self, "async_set_unique_id", None)
            if callable(set_uid):
                await set_uid(self._data["plant_id"])
            abort = getattr(self, "_abort_if_unique_id_configured", None)
            if callable(abort):
                abort()

            return self.async_create_entry(
                title=self._data["plant_name"],
                data=self._data,
            )

        return self.async_show_form(step_id="user", data_schema=data_schema)


class HorticultureAssistantOptionsFlow(config_entries.OptionsFlow):
    """Handle options for an existing Horticulture Assistant entry."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry
        self._data = dict(entry.data)

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Edit optional details and sensors."""
        if user_input is not None:
            for key in ("moisture_sensors", "temperature_sensors"):
                if key in user_input and isinstance(user_input[key], str):
                    user_input[key] = [s.strip() for s in user_input[key].split(",") if s.strip()]
            self._data.update(user_input)
            plant_id = generate_profile(self._data, overwrite=True)
            if plant_id:
                self._data["plant_id"] = plant_id
                self._data["profile_generated"] = True
            return self.async_create_entry(title="", data=self._data)

        data_schema = vol.Schema({
            vol.Optional(
                "plant_type", default=self.entry.data.get("plant_type", "")
            ): TextSelector(),
            vol.Optional(
                "cultivar", default=self.entry.data.get("cultivar", "")
            ): TextSelector(),
            vol.Optional("zone_id", default=self.entry.data.get("zone_id", "")):
                TextSelector(),
            vol.Optional(
                CONF_ENABLE_AUTO_APPROVE,
                default=self.entry.data.get(CONF_ENABLE_AUTO_APPROVE, False),
            ): BooleanSelector(),
            vol.Optional(
                "moisture_sensors",
                default=self.entry.data.get("moisture_sensors", []),
            ): EntitySelector({"domain": "sensor", "multiple": True}),
            vol.Optional(
                "temperature_sensors",
                default=self.entry.data.get("temperature_sensors", []),
            ): EntitySelector({"domain": "sensor", "multiple": True}),
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)


async def async_get_options_flow(
    config_entry: config_entries.ConfigEntry,
) -> HorticultureAssistantOptionsFlow:
    """Return the options flow handler."""
    return HorticultureAssistantOptionsFlow(config_entry)


class PlantProfileSubEntryFlow(config_entries.ConfigSubentryFlow):
    """Handle subentry flows for additional plant profiles."""

    async def async_step_user(self, user_input: dict | None = None) -> config_entries.SubentryFlowResult:
        """Create a new plant profile entry."""
        data_schema = vol.Schema({
            vol.Required("plant_name"): TextSelector(),
            vol.Optional("zone_id"): TextSelector(),
        })

        if user_input is not None:
            plant_id = generate_profile(user_input, self.hass)
            if plant_id:
                user_input["profile_generated"] = True
                user_input["plant_id"] = plant_id
            else:
                user_input["profile_generated"] = False
                user_input["plant_id"] = f"pending_{uuid4().hex}"
            return self.async_create_entry(
                title=user_input["plant_name"],
                data=user_input,
                unique_id=user_input["plant_id"],
            )

        return self.async_show_form(step_id="user", data_schema=data_schema)


@callback
def async_get_supported_subentry_types(
    config_entry: config_entries.ConfigEntry,
) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
    """Return the subentry flow handler mapping."""
    return {"plant": PlantProfileSubEntryFlow}

