"""Config flow for Horticulture Assistant integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    BooleanSelector,
    TextSelector,
)

from .const import DOMAIN


class HorticultureAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Horticulture Assistant."""

    VERSION = 1  # Bump this if breaking changes are made to stored entries
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title="Horticulture Assistant", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("enable_auto_approve"): BooleanSelector(),
                    vol.Optional("default_threshold_mode", default="manual"): vol.In(["manual", "profile"]),
                }
            ),
            description_placeholders={
                "info": "Enable auto-approve for automations like irrigation or fertilization. Choose if you want thresholds manually entered or pulled from plant profiles."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Return the options flow handler."""
        return HorticultureAssistantOptionsFlow(config_entry)


class HorticultureAssistantOptionsFlow(config_entries.OptionsFlow):
    """Handle a config options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("enable_auto_approve", default=current.get("enable_auto_approve", False)): BooleanSelector(),
                    vol.Required("default_threshold_mode", default=current.get("default_threshold_mode", "manual")): vol.In(["manual", "profile"]),
                }
            ),
        )