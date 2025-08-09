from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from .const import (
    DOMAIN, CONF_API_KEY, CONF_MODEL, CONF_BASE_URL, CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL, DEFAULT_MODEL, DEFAULT_UPDATE_MINUTES,
)

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
    vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): str,
    vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_MINUTES): int,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc,call-arg]
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Horticulture Assistant", data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_MODEL: self._entry.data.get(CONF_MODEL, DEFAULT_MODEL),
            CONF_BASE_URL: self._entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            CONF_UPDATE_INTERVAL: self._entry.options.get(CONF_UPDATE_INTERVAL,
                self._entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES)),
        }
        schema = vol.Schema({
            vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
            vol.Optional(CONF_BASE_URL, default=defaults[CONF_BASE_URL]): str,
            vol.Optional(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): int,
        })
        return self.async_show_form(step_id="init", data_schema=schema)
