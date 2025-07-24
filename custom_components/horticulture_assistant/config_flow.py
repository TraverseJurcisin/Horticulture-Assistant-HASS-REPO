"""Config flow for Horticulture Assistant integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import BooleanSelector, TextSelector

from .const import DOMAIN, CONF_ENABLE_AUTO_APPROVE

class HorticultureAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Horticulture Assistant."""
    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            # Create a config entry with the plant name as the title
            return self.async_create_entry(title=user_input["plant_name"], data=user_input)

        data_schema = vol.Schema({
            vol.Required("plant_name"): TextSelector(),
            vol.Required("zone_id"): TextSelector(),
            vol.Required(CONF_ENABLE_AUTO_APPROVE, default=False): BooleanSelector(),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema
        )
