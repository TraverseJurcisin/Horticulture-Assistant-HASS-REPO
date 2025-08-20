from homeassistant.const import Platform
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "horticulture_assistant"
# The integration exposes multiple entity platforms per plant
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

CONF_API_KEY = "api_key"
CONF_MODEL = "model"
CONF_BASE_URL = "base_url"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MOISTURE_SENSOR = "moisture_sensor"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_EC_SENSOR = "ec_sensor"
CONF_CO2_SENSOR = "co2_sensor"
CONF_KEEP_STALE = "keep_stale"
CONF_PLANT_NAME = "plant_name"
CONF_PLANT_ID = "plant_id"
CONF_PLANT_TYPE = "plant_type"

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"  # change to "gpt-5" if your account has it
DEFAULT_UPDATE_MINUTES = 5
DEFAULT_KEEP_STALE = True

# Entity categories
CATEGORY_DIAGNOSTIC = EntityCategory.DIAGNOSTIC
CATEGORY_CONTROL = EntityCategory.CONFIG
