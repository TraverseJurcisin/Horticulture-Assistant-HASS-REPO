"""Central constants used across the plant engine."""

from __future__ import annotations

# Multipliers used to scale nutrient recommendations based on lifecycle stage.
STAGE_MULTIPLIERS: dict[str, float] = {
    "seedling": 0.5,
    "vegetative": 1.0,
    "flowering": 1.2,
    "fruiting": 1.1,
}

# Default environment readings applied when a plant profile lacks recent data.
DEFAULT_ENV: dict[str, float] = {
    "temp_c": 26,
    "temp_c_max": 30,
    "temp_c_min": 22,
    "rh_pct": 65,
    "par_w_m2": 350,
    "wind_speed_m_s": 1.2,
}

# Dataset filenames used across the engine. Centralizing these paths helps
# maintain consistency when loading data files and allows easy updates.
ENV_SCORE_WEIGHTS_FILE = "environment_score_weights.json"
