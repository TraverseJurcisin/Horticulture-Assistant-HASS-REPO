"""Simple irrigation automation using local plant profiles.

The module scans the ``plants`` directory for profile files and triggers
irrigation actuators when the current soil moisture reading falls below the
configured threshold.  It is intentionally lightweight so that it can be used
as a standalone script or invoked from Home Assistant services.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from custom_components.horticulture_assistant.utils.path_utils import plants_path

from .helpers import append_json_log, iter_profiles, latest_env

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
            if isinstance(val, list | tuple):
                val = val[0]
            try:
                return float(val)
            except (TypeError, ValueError):
                return None
    return None


def _get_current_moisture(profile: dict) -> float | None:
    """Return latest soil moisture reading from profile data."""

    data = latest_env(profile)
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


def run_automation_cycle(base_path: str | None = None) -> None:
    """
    Run one cycle of automated irrigation checks for all plant profiles.
    Scans the plants directory for profile JSON files, checks soil moisture
    against thresholds, and triggers irrigation actuators if needed.

    ``base_path`` defaults to the configured ``plants`` directory.
    """
    # Global override check
    if not ENABLE_AUTOMATION:
        _LOGGER.info("Automation is globally disabled (ENABLE_AUTOMATION=False). Skipping automation cycle.")
        return

    if base_path is None:
        base_path = plants_path(None)
    plants_dir = Path(base_path)
    if not plants_dir.is_dir():
        _LOGGER.error("Plants directory not found: %s", plants_dir)
        return

    profiles = iter_profiles(base_path)
    found = False

    for plant_id, profile_data in profiles:
        found = True
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
                    plant_id=plant_id,
                    trigger=True,
                    base_path=base_path,
                )
            except Exception as e:  # noqa: BLE001 - best effort logging
                _LOGGER.error(
                    "Failed to trigger irrigation actuator for plant %s: %s",
                    plant_id,
                    e,
                )
            else:
                triggered = True
        else:
            _LOGGER.info(
                "Soil moisture sufficient for plant %s (%.2f >= %.2f).",
                plant_id,
                info.current,
                info.threshold,
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
        except Exception as e:  # noqa: BLE001 - log and continue
            _LOGGER.error("Failed to write irrigation log for plant %s: %s", plant_id, e)

    if not found:
        _LOGGER.info("No plant profile JSON files found in %s. Nothing to do.", plants_dir)
