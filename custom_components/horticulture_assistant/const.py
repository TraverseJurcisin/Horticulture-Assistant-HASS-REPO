from __future__ import annotations

from typing import TypedDict

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    Platform,
    UnitOfIlluminance,
    UnitOfTemperature,
)
from homeassistant.helpers.entity import EntityCategory

DOMAIN = "horticulture_assistant"
# The integration exposes multiple entity platforms per plant
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]


class PlantSensorMetadata(TypedDict, total=False):
    """Metadata describing a plant sensor type."""

    name: str
    device_class: SensorDeviceClass | str
    unit: str
    icon: str


# Fixed sensor types for each plant profile (TODO: only create sensors that are needed)
PLANT_SENSOR_TYPES: dict[str, PlantSensorMetadata] = {
    "air_temperature": {
        "name": "Air Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
    },
    "air_humidity": {
        "name": "Air Humidity",
        "device_class": SensorDeviceClass.HUMIDITY,
        "unit": PERCENTAGE,
        "icon": "mdi:water-percent",
    },
    "soil_moisture": {
        "name": "Soil Moisture",
        "device_class": SensorDeviceClass.MOISTURE,
        "unit": PERCENTAGE,
        "icon": "mdi:water-percent",
    },
    "soil_temperature": {
        "name": "Soil Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "unit": UnitOfTemperature.CELSIUS,
        "icon": "mdi:thermometer",
    },
    "light_intensity": {
        "name": "Light Intensity",
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "unit": UnitOfIlluminance.LUX,
        "icon": "mdi:brightness-5",
    },
    "co2": {
        "name": "CO2",  # carbon dioxide concentration
        "device_class": SensorDeviceClass.CO2,
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "icon": "mdi:molecule-co2",
    },
    # ... add other sensor types if needed (e.g., light dli, vpd, etc.) ...
}

SIGNAL_PROFILE_CONTEXTS_UPDATED = "horticulture_profile_contexts_updated"

# Home Assistant event types fired when profile history is updated.
EVENT_PROFILE_RUN_RECORDED = "horticulture_assistant_profile_run_recorded"
EVENT_PROFILE_HARVEST_RECORDED = "horticulture_assistant_profile_harvest_recorded"
EVENT_PROFILE_NUTRIENT_RECORDED = "horticulture_assistant_profile_nutrient_recorded"
EVENT_PROFILE_CULTIVATION_RECORDED = "horticulture_assistant_profile_cultivation_recorded"
EVENT_YIELD_UPDATE = "horticulture_assistant_yield_update"

# Normalised status strings used across entities, triggers and conditions.
STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_CRITICAL = "critical"
STATUS_STATES_PROBLEM: tuple[str, ...] = (STATUS_WARN, STATUS_CRITICAL)
STATUS_STATES_RECOVERED: tuple[str, ...] = (STATUS_OK,)

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

PROFILE_ID_PATTERN = r"^[a-z0-9_]+$"
PROFILE_ID_MAX_LENGTH = 32

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
NOTIFICATION_PROFILE_LINEAGE = "horticulture_profile_lineage"
NOTIFICATION_PROFILE_SENSORS = "horticulture_profile_sensors"
NOTIFICATION_DATASET_HEALTH = "horticulture_dataset_health"

# Issue registry identifiers
ISSUE_PROFILE_VALIDATION_PREFIX = "invalid_profile_"
ISSUE_PROFILE_SENSOR_PREFIX = "missing_sensor_"
ISSUE_DATASET_HEALTH_PREFIX = "dataset_health_"

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


def signal_profile_contexts_updated(entry_id: str | None) -> str:
    """Return the dispatcher signal for profile context updates."""

    base = SIGNAL_PROFILE_CONTEXTS_UPDATED
    if not entry_id:
        return base
    return f"{base}_{entry_id}"
