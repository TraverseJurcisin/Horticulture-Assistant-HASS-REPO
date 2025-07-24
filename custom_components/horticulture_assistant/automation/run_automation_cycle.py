"""Simple irrigation automation using local plant profiles."""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from .helpers import iter_profiles, append_json_log

# Global override: disable automation if False
ENABLE_AUTOMATION = False

_LOGGER = logging.getLogger(__name__)


def _irrigation_enabled(profile: dict) -> bool:
    """Return ``True`` if irrigation automation is enabled for the profile."""

    if profile.get("irrigation_enabled") is False:
        return False
    gen = profile.get("general")
    if isinstance(gen, dict) and gen.get("irrigation_enabled") is False:
        return False
    acts = profile.get("actuators")
    if isinstance(acts, dict):
        return acts.get("irrigation_enabled", True)
    return True


def _get_moisture_threshold(profile: dict) -> float | None:
    """Return soil moisture threshold value if defined."""

    thresholds = profile.get("thresholds", {})
    for key in ("soil_moisture_min", "soil_moisture_pct", "soil_moisture"):
        if key in thresholds:
            val = thresholds[key]
            if isinstance(val, (list, tuple)):
                val = val[0]
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    return None


def _get_current_moisture(profile: dict) -> float | None:
    """Return latest soil moisture reading from profile data."""

    data = {}
    gen = profile.get("general")
    if isinstance(gen, dict):
        data = gen.get("latest_env", {}) or {}
    if not data:
        data = profile.get("latest_env", {})
    for key in ("soil_moisture", "soil_moisture_pct", "moisture", "vwc"):
        if key in data:
            try:
                return float(data[key])
            except (TypeError, ValueError):
                return None
    return None


@dataclass(slots=True)
class MoistureInfo:
    """Current reading and threshold for irrigation checks."""

    current: float
    threshold: float

def run_automation_cycle(base_path: str = "plants") -> None:
    """
    Run one cycle of automated irrigation checks for all plant profiles.
    Scans the plants directory for profile JSON files, checks soil moisture against thresholds,
    and triggers irrigation actuators if needed.
    """
    # Global override check
    if not ENABLE_AUTOMATION:
        _LOGGER.info("Automation is globally disabled (ENABLE_AUTOMATION=False). Skipping automation cycle.")
        return

    plants_dir = Path(base_path)
    if not plants_dir.is_dir():
        _LOGGER.error("Plants directory not found: %s", plants_dir)
        return

    profiles = list(iter_profiles(base_path))
    if not profiles:
        _LOGGER.info("No plant profile JSON files found in %s. Nothing to do.", plants_dir)
        return

    for plant_id, profile_data in profiles:
        if not _irrigation_enabled(profile_data):
            _LOGGER.info("Irrigation disabled for plant %s. Skipping.", plant_id)
            continue

        threshold = _get_moisture_threshold(profile_data)
        current = _get_current_moisture(profile_data)
        if threshold is None or current is None:
            _LOGGER.error("Missing moisture data for plant %s. Skipping.", plant_id)
            continue

        info = MoistureInfo(current=current, threshold=threshold)

        triggered = False
        if info.current < info.threshold:
            _LOGGER.info(
                "Soil moisture below threshold for %s (%.2f < %.2f). Triggering irrigation.",
                plant_id,
                info.current,
                info.threshold,
            )
            try:
                import custom_components.horticulture_assistant.automation.irrigation_actuator as irrigation_actuator
                irrigation_actuator.trigger_irrigation_actuator(
                    plant_id=plant_id, trigger=True, base_path=base_path
                )
            except Exception as e:  # noqa: BLE001
                _LOGGER.error(
                    "Failed to trigger irrigation actuator for plant %s: %s", plant_id, e
                )
            else:
                triggered = True
        else:
            _LOGGER.info(
                "Soil moisture sufficient for plant %s (%.2f >= %.2f).", plant_id, info.current, info.threshold
            )

        entry = {
            "timestamp": datetime.now().isoformat(),
            "soil_moisture": info.current,
            "threshold": info.threshold,
            "triggered": triggered,
        }
        log_file = plants_dir / str(plant_id) / "irrigation_log.json"
        try:
            append_json_log(log_file, entry)
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to write irrigation log for plant %s: %s", plant_id, e)
