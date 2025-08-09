from homeassistant.const import Platform

DOMAIN = "horticulture_assistant"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_BASE_URL = "base_url"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MOISTURE_SENSOR = "moisture_sensor"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_EC_SENSOR = "ec_sensor"
CONF_CO2_SENSOR = "co2_sensor"
CONF_KEEP_STALE = "keep_stale"

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"  # change to "gpt-5" if your account has it
DEFAULT_UPDATE_MINUTES = 5
DEFAULT_KEEP_STALE = True
