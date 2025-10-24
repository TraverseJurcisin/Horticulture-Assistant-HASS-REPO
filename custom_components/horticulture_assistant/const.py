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
CONF_CLOUD_SYNC_ENABLED = "cloud_sync_enabled"
CONF_CLOUD_BASE_URL = "cloud_base_url"
CONF_CLOUD_TENANT_ID = "cloud_tenant_id"
CONF_CLOUD_DEVICE_TOKEN = "cloud_device_token"
CONF_CLOUD_SYNC_INTERVAL = "cloud_sync_interval"
CONF_CLOUD_ACCOUNT_EMAIL = "cloud_account_email"
CONF_CLOUD_ACCESS_TOKEN = "cloud_access_token"
CONF_CLOUD_REFRESH_TOKEN = "cloud_refresh_token"
CONF_CLOUD_TOKEN_EXPIRES_AT = "cloud_token_expires_at"
CONF_CLOUD_ACCOUNT_ROLES = "cloud_account_roles"
CONF_CLOUD_ORGANIZATION_ID = "cloud_org_id"
CONF_CLOUD_ORGANIZATION_NAME = "cloud_org_name"
CONF_CLOUD_ORGANIZATION_ROLE = "cloud_org_role"
CONF_CLOUD_AVAILABLE_ORGANIZATIONS = "cloud_available_orgs"
CONF_CLOUD_FEATURE_FLAGS = "cloud_feature_flags"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_MOISTURE_SENSOR = "moisture_sensor"
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_EC_SENSOR = "ec_sensor"
CONF_CO2_SENSOR = "co2_sensor"
CONF_KEEP_STALE = "keep_stale"
CONF_PLANT_NAME = "plant_name"
CONF_PLANT_ID = "plant_id"
CONF_PLANT_TYPE = "plant_type"
CONF_PROFILES = "profiles"

CONF_PROFILE_SCOPE = "profile_scope"

PROFILE_SCOPE_DEFAULT = "individual"
PROFILE_SCOPE_CHOICES = (
    "individual",
    "species_template",
    "crop_batch",
    "grow_zone",
)

# Variables (keys) we support in thresholds (can extend safely)
VARIABLE_SPECS = [
    # key, unit, step, min, max
    ("temp_c_min", "°C", 0.1, -20, 60),
    ("temp_c_max", "°C", 0.1, -20, 60),
    ("rh_min", "%", 1, 0, 100),
    ("rh_max", "%", 1, 0, 100),
    ("dli_min", "mol/m²·d", 0.1, 0, 60),
    ("dli_max", "mol/m²·d", 0.1, 0, 60),
    ("moisture_min", "%", 1, 0, 100),
    ("moisture_max", "%", 1, 0, 100),
    ("ec_min", "µS/cm", 1, 0, 20000),
    ("ec_max", "µS/cm", 1, 0, 20000),
    ("co2_min", "ppm", 10, 300, 2000),
    ("co2_max", "ppm", 10, 300, 5000),
    ("vpd_min", "kPa", 0.01, 0, 3),
    ("vpd_max", "kPa", 0.01, 0, 3),
]
OPB_FIELD_MAP = {
    "temp_c_min": "temperature.min_c",
    "temp_c_max": "temperature.max_c",
    "rh_min": "humidity.min",
    "rh_max": "humidity.max",
    "dli_min": "light.dli_min",
    "dli_max": "light.dli_max",
    "moisture_min": "soil_moisture.min",
    "moisture_max": "soil_moisture.max",
    "ec_min": "ec.min",
    "ec_max": "ec.max",
    "co2_min": "co2.min",
    "co2_max": "co2.max",
    "vpd_min": "vpd.min",
    "vpd_max": "vpd.max",
}
SOURCES = ("manual", "clone", "opb", "ai")

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"  # change to "gpt-5" if your account has it
DEFAULT_UPDATE_MINUTES = 5
DEFAULT_KEEP_STALE = True
DEFAULT_CLOUD_SYNC_INTERVAL = 300

# Persistent notification identifiers
NOTIFICATION_PROFILE_VALIDATION = "horticulture_profile_validation"
NOTIFICATION_DATASET_HEALTH = "horticulture_dataset_health"

# ---------------------------------------------------------------------------
# Feature & entitlement constants
# ---------------------------------------------------------------------------

FEATURE_LOCAL_PROFILES = "local_profiles"
FEATURE_CLOUD_SYNC = "cloud_sync"
FEATURE_AI_ASSIST = "ai_assist"
FEATURE_IRRIGATION_AUTOMATION = "irrigation_automation"
FEATURE_ADVANCED_ANALYTICS = "advanced_analytics"
FEATURE_ORGANIZATION_ADMIN = "organization_admin"

PREMIUM_FEATURES: tuple[str, ...] = (
    FEATURE_AI_ASSIST,
    FEATURE_IRRIGATION_AUTOMATION,
    FEATURE_ADVANCED_ANALYTICS,
    FEATURE_ORGANIZATION_ADMIN,
)

# Entity categories
CATEGORY_DIAGNOSTIC = EntityCategory.DIAGNOSTIC
CATEGORY_CONTROL = EntityCategory.CONFIG
