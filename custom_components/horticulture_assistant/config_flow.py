"""Config flow for Horticulture Assistant integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import BooleanSelector, TextSelector

from .utils.profile_generator import generate_profile

from .const import DOMAIN, CONF_ENABLE_AUTO_APPROVE

class HorticultureAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Horticulture Assistant."""

    VERSION = 1

    def __init__(self) -> None:
        self._data: dict = {}

    async def async_step_user(self, user_input: dict | None = None) -> FlowResult:
        """Handle the initial step collecting the plant id."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_details()

        data_schema = vol.Schema({
            vol.Required("plant_name"): TextSelector(),
            vol.Optional("zone_id"): TextSelector(),
            vol.Optional(CONF_ENABLE_AUTO_APPROVE, default=False): BooleanSelector(),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_details(self, user_input: dict | None = None) -> FlowResult:
        """Collect optional plant details."""
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()

        data_schema = vol.Schema({
            vol.Optional("plant_type"): TextSelector(),
            vol.Optional("cultivar"): TextSelector(),
        })

        return self.async_show_form(step_id="details", data_schema=data_schema)

    async def async_step_sensors(self, user_input: dict | None = None) -> FlowResult:
        """Ask for sensor entity ids and finish."""
        if user_input is not None:
            for key in ("moisture_sensors", "temperature_sensors"):
                if key in user_input and isinstance(user_input[key], str):
                    user_input[key] = [s.strip() for s in user_input[key].split(",") if s.strip()]
            self._data.update(user_input)
            generate_profile(self._data)
            return self.async_create_entry(title=self._data["plant_name"], data=self._data)

        data_schema = vol.Schema({
            vol.Optional("moisture_sensors"): TextSelector(),
            vol.Optional("temperature_sensors"): TextSelector(),
        })

        return self.async_show_form(step_id="sensors", data_schema=data_schema)
