"""Helpers for generating simple daily plant reports from sensor data."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from homeassistant.core import HomeAssistant

from custom_components.horticulture_assistant.utils.bio_profile_loader import (
    load_profile,
)
from custom_components.horticulture_assistant.utils.path_utils import (
    config_path,
    data_path,
    plants_path,
)
from custom_components.horticulture_assistant.utils.plant_registry import (
    PLANT_REGISTRY_FILE,
)
from plant_engine import environment_manager

from .json_io import load_json, save_json
from .state_helpers import (
    aggregate_sensor_values,
    get_numeric_state,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class DailyReport:
    """Lightweight representation of a daily plant report."""

    plant_id: str
    timestamp: str
    lifecycle_stage: str
    moisture: float | None
    ec: float | None
    temperature: float | None
    humidity: float | None
    light: float | None
    yield_amount: float | None
    thresholds: dict
    nutrients: dict
    tags: list[str]
    environment_targets: dict
    ai_feedback_required: bool

    def as_dict(self) -> dict:
        return asdict(self)


__all__ = ["DailyReport", "build_daily_report"]


def _resolve_plant_type(hass: HomeAssistant, plant_id: str, profile: dict) -> str | None:
    """Return plant type from profile or plant registry if available."""
    ptype = profile.get("general", {}).get("plant_type")
    if ptype:
        return str(ptype)
    reg_path = config_path(hass, PLANT_REGISTRY_FILE)
    try:
        reg = load_json(reg_path)
        return reg.get(plant_id, {}).get("plant_type")
    except Exception:
        return None


def _report_path(base: Path, plant_id: str) -> Path:
    """Return file path for today's report under ``base``."""
    date_str = datetime.now().strftime("%Y%m%d")
    return base / f"{plant_id}-{date_str}.json"


def build_daily_report(hass: HomeAssistant, plant_id: str) -> dict:
    """Collect current sensor data and profile info for a plant and compile a daily report."""
    # Load plant profile (JSON or YAML) by plant_id
    profile = load_profile(plant_id=plant_id, base_dir=plants_path(hass))
    if not profile:
        _LOGGER.error("Plant profile for '%s' not found or empty.", plant_id)
        return {}

    # Determine current lifecycle stage from profile (if available)
    stage = (
        profile.get("general", {}).get("lifecycle_stage")
        or profile.get("general", {}).get("stage")
        or "unknown"
    )
    plant_type = _resolve_plant_type(hass, plant_id, profile)
    env_targets = (
        environment_manager.get_environmental_targets(plant_type, stage) if plant_type else {}
    )

    # Static thresholds and nutrient targets from profile
    thresholds = profile.get("thresholds", {})  # environmental or nutrient thresholds
    nutrient_targets = profile.get("nutrients", {})  # target nutrient levels
    # Tags may be defined at root or under 'general'
    tags = profile.get("general", {}).get("tags") or profile.get("tags") or []
    if tags is None:
        tags = []

    # Collect current sensor readings (moisture, EC, temperature, humidity, light)
    sensor_map = (
        profile.get("sensor_entities") or profile.get("general", {}).get("sensor_entities") or {}
    )

    def _aggregate(key: str, default_id: str) -> float | None:
        val = sensor_map.get(key, default_id)
        return aggregate_sensor_values(hass, val)

    moisture = _aggregate("moisture_sensors", f"sensor.{plant_id}_raw_moisture")
    ec = _aggregate("ec_sensors", f"sensor.{plant_id}_raw_ec")
    temperature = _aggregate("temperature_sensors", f"sensor.{plant_id}_raw_temperature")
    humidity = _aggregate("humidity_sensors", f"sensor.{plant_id}_raw_humidity")
    light = _aggregate("light_sensors", f"sensor.{plant_id}_raw_light")

    # Last known yield (e.g., total yield or current yield progress)
    yield_val = profile.get("last_yield")
    if yield_val is None:
        # Attempt to retrieve from a yield sensor if available (e.g., integration's Yield Progress sensor)
        short_id = plant_id[:6]
        possible_yield_entities = [
            f"sensor.{plant_id}_yield",
            f"sensor.plant_{short_id}_yield_progress",
        ]
        for ent in possible_yield_entities:
            y_state = get_numeric_state(hass, ent)
            if y_state is not None:
                yield_val = y_state
                break

    # Compile the daily report structure
    report = DailyReport(
        plant_id=plant_id,
        timestamp=datetime.now().isoformat(),
        lifecycle_stage=stage,
        moisture=moisture,
        ec=ec,
        temperature=temperature,
        humidity=humidity,
        light=light,
        yield_amount=yield_val,
        thresholds=thresholds,
        nutrients=nutrient_targets,
        tags=tags,
        environment_targets=env_targets,
        ai_feedback_required=not profile.get("auto_approve_all", False),
    )

    # Save report to disk (under data/daily_reports/<plant_id>-YYYYMMDD.json)
    report_dir = data_path(hass, "daily_reports")
    os.makedirs(report_dir, exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d")
    file_path = os.path.join(report_dir, f"{plant_id}-{date_str}.json")
    try:
        save_json(file_path, report.as_dict())
        _LOGGER.info("Daily report saved for plant %s at %s", plant_id, file_path)
    except Exception as e:
        _LOGGER.error("Failed to save daily report for %s: %s", plant_id, e)

    return report
