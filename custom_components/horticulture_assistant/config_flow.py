from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector as sel
from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_MODEL,
    CONF_BASE_URL,
    CONF_UPDATE_INTERVAL,
    CONF_MOISTURE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_EC_SENSOR,
    CONF_CO2_SENSOR,
    CONF_KEEP_STALE,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DEFAULT_KEEP_STALE,
)
from .api import ChatApi

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): str,
    vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): str,
    vol.Optional(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_MINUTES): vol.All(
        int, vol.Range(min=1)
    ),
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc,call-arg]
    VERSION = 2

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
            except Exception:
                errors["base"] = "cannot_connect"
            if not errors:
                return self.async_create_entry(title="Horticulture Assistant", data=user_input)
        return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)

class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self._entry = entry

    async def async_step_init(self, user_input=None):
        defaults = {
            CONF_MODEL: self._entry.data.get(CONF_MODEL, DEFAULT_MODEL),
            CONF_BASE_URL: self._entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            CONF_UPDATE_INTERVAL: self._entry.options.get(
                CONF_UPDATE_INTERVAL,
                self._entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
            ),
            CONF_KEEP_STALE: self._entry.options.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
        }

        schema = vol.Schema(
            {
                vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
                vol.Optional(CONF_BASE_URL, default=defaults[CONF_BASE_URL]): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): int,
                vol.Optional(CONF_MOISTURE_SENSOR): vol.Any(
                    sel.EntitySelector(
                        sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])
                    ),
                    str,
                ),
                vol.Optional(CONF_TEMPERATURE_SENSOR): vol.Any(
                    sel.EntitySelector(
                        sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])
                    ),
                    str,
                ),
                vol.Optional(CONF_EC_SENSOR): vol.Any(
                    sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"])),
                    str,
                ),
                vol.Optional(CONF_CO2_SENSOR): vol.Any(
                    sel.EntitySelector(
                        sel.EntitySelectorConfig(domain=["sensor"], device_class=["carbon_dioxide"])
                    ),
                    str,
                ),
                vol.Optional(CONF_KEEP_STALE, default=defaults[CONF_KEEP_STALE]): bool,
            }
        )

        errors = {}
        if user_input is not None:
            if user_input.get(CONF_UPDATE_INTERVAL, 1) < 1:
                errors[CONF_UPDATE_INTERVAL] = "invalid_interval"
            for key in (CONF_MOISTURE_SENSOR, CONF_TEMPERATURE_SENSOR, CONF_EC_SENSOR, CONF_CO2_SENSOR):
                entity_id = user_input.get(key)
                if entity_id and self.hass.states.get(entity_id) is None:
                    errors[key] = "not_found"
            if errors:
                return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(step_id="init", data_schema=schema)


# Backwards compatibility for older imports
class HorticultureAssistantConfigFlow(ConfigFlow):
    """Retain legacy class name for tests and external references."""
    pass
