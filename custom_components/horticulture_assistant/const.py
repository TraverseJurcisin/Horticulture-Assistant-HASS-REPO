"""Constants for the Horticulture Assistant integration."""

# Domain metadata
DOMAIN = "horticulture_assistant"
VERSION = "0.1.0"
ISSUE_URL = "https://github.com/TraverseJurcisin/Horticulture-Assistant/issues"

# Service names
SERVICE_UPDATE_SENSORS = "update_sensors"

# Platform support
PLATFORMS = ["sensor", "binary_sensor", "switch"]

# Configuration
CONF_ENABLE_AUTO_APPROVE = "enable_auto_approve"
CONF_DEFAULT_THRESHOLD_MODE = "default_threshold_mode"
CONF_USE_OPENAI = "use_openai"
CONF_OPENAI_MODEL = "openai_model"
CONF_OPENAI_API_KEY = "openai_api_key"

# Threshold modes
THRESHOLD_MODE_MANUAL = "manual"
THRESHOLD_MODE_PROFILE = "profile"

# Data keys
DATA_KEY_COORDINATOR = "coordinator"

# Default values
DEFAULT_UPDATE_INTERVAL = 300  # seconds

# Sensor types
SENSOR_TYPE_MOISTURE = "moisture"
SENSOR_TYPE_TEMPERATURE = "temperature"
SENSOR_TYPE_HUMIDITY = "humidity"
SENSOR_TYPE_LIGHT = "par"
SENSOR_TYPE_EC = "electrical_conductivity"
SENSOR_TYPE_PH = "ph"
SENSOR_TYPE_VWC = "volumetric_water_content"
SENSOR_TYPE_ET = "evapotranspiration"

# Entity categories
CATEGORY_DIAGNOSTIC = "diagnostic"
CATEGORY_CONTROL = "control"
CATEGORY_MONITORING = "monitoring"
CATEGORY_CALIBRATION = "calibration"

# Units
UNIT_PERCENT = "%"
UNIT_CELSIUS = "°C"
UNIT_MOLES_PER_M2S = "mol/m²/s"
UNIT_MS_CM = "mS/cm"
UNIT_PH = "pH"
UNIT_MM_DAY = "mm/day"
UNIT_GRAMS = "g"
UNIT_LITERS = "L"
UNIT_PPM = "ppm"

# Custom events
EVENT_AI_RECOMMENDATION = "horticulture_ai_recommendation"
EVENT_YIELD_UPDATE = "horticulture_yield_update"

# Tags for plant profile aggregation
TAG_CULTIVAR = "cultivar"
TAG_SPECIES = "species"
TAG_GENUS = "genus"
TAG_FAMILY = "family"
TAG_CLIMATE = "climate"

# Smoothing factor for exponential moving averages used by sensors
MOVING_AVERAGE_ALPHA = 0.6
