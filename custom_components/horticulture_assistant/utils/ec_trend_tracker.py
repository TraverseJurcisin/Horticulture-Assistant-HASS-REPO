# File: custom_components/horticulture_assistant/utils/ec_trend_tracker.py

"""
Utility for tracking EC trends and alerting on rapid changes or sustained high EC levels.
Accepts a plant ID and analyzes recent electrical conductivity (EC) sensor readings to detect:
- Sudden increases (e.g., rise > 1.0 mS/cm within 3 hours)
- Sustained high EC above the plant's threshold for an extended period

Any detected alerts are logged and recorded in a JSON file (`data/ec_alerts.json`).
"""

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Optional

from custom_components.horticulture_assistant.utils.path_utils import data_path, plants_path

# Attempt to import HomeAssistant for type hints and runtime (if running inside HA)
try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None  # type: ignore

# Import Home Assistant history function for state changes, if available
try:
    from homeassistant.components.recorder.history import state_changes_during_period
except ImportError:
    state_changes_during_period = None  # type: ignore

# Import plant profile loader to retrieve sensor mapping and thresholds
try:
    from custom_components.horticulture_assistant.utils.bio_profile_loader import load_profile
except ImportError:
    load_profile = None

_LOGGER = logging.getLogger(__name__)

# Thresholds for alert conditions
SUDDEN_CHANGE_THRESHOLD = 1.0  # mS/cm increase
SUDDEN_CHANGE_WINDOW_HOURS = 3  # hours for sudden change detection
SUSTAINED_HIGH_WINDOW_HOURS = 6  # hours for sustained high EC detection


class ECTrendTracker:
    def __init__(self, data_file: str | None = None, hass: Optional['HomeAssistant'] = None):
        """
        Initialize the ECTrendTracker.
        Loads existing EC alert logs from the specified JSON file, or creates a new structure if file is absent.
        :param data_file: Path to the EC alert log JSON file.
        Defaults to 'data/ec_alerts.json' in Home Assistant config.
        :param hass: HomeAssistant instance (optional) for sensor data access and path resolution.
        """
        # Determine the data file path
        if data_file is None:
            # Use Home Assistant config directory if available
            data_file = data_path(hass, "ec_alerts.json")
        self._data_file = data_file
        self._hass = hass
        # Internal alerts log structure: dict of plant_id -> list of alert entries
        self._alerts: dict[str, list[dict]] = {}
        # Load existing alerts from file if available
        try:
            with open(self._data_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for pid, entries in data.items():
                    if isinstance(entries, list):
                        self._alerts[pid] = entries
                    else:
                        _LOGGER.warning("EC alert log for plant %s is not a list; resetting to empty list.", pid)
                        self._alerts[pid] = []
            else:
                _LOGGER.warning("EC alerts file format invalid (expected dict); starting with empty alerts log.")
        except FileNotFoundError:
            _LOGGER.info("EC alerts file not found at %s; starting new EC alerts log.", self._data_file)
        except json.JSONDecodeError as e:
            _LOGGER.error(
                "JSON decode error reading EC alerts from %s: %s; initializing empty alert log.",
                self._data_file,
                e,
            )
        except Exception as e:
            _LOGGER.error(
                "Error loading EC alerts from %s: %s; initializing empty alert log.",
                self._data_file,
                e,
            )

    def check_trends(self, plant_id: str) -> None:
        """
        Analyze recent EC sensor readings for the given plant and flag any significant EC trend alerts.
        Flags:
          - Sudden increase in EC (> SUDDEN_CHANGE_THRESHOLD within SUDDEN_CHANGE_WINDOW_HOURS).
          - Sustained high EC above plant's threshold for > SUSTAINED_HIGH_WINDOW_HOURS.
        Logs any detected alerts and records them in the EC alerts log.
        """
        if self._hass is None:
            _LOGGER.error("HomeAssistant instance not provided; cannot retrieve sensor data for trend analysis.")
            return
        if state_changes_during_period is None:
            _LOGGER.warning(
                "History not available; EC trend analysis cannot be performed for plant %s.",
                plant_id,
            )
            return

        # Load plant profile to get sensor entity and threshold
        profile = {}
        if load_profile is not None:
            profile = load_profile(plant_id=plant_id, base_dir=plants_path(self._hass))
        if not profile:
            _LOGGER.error(
                "Plant profile for '%s' not found or empty. EC threshold will be unavailable.",
                plant_id,
            )

        sensor_map = profile.get("sensor_entities") or {}
        ec_entity = sensor_map.get("ec") or f"sensor.{plant_id}_raw_ec"
        # Retrieve the plant's EC threshold from profile (if available)
        plant_threshold: float | None = None
        thresholds = profile.get("thresholds") if profile else {}
        if isinstance(thresholds, dict):
            # Look for an EC threshold key (case-insensitive match: "EC", "ec")
            for key, value in thresholds.items():
                if str(key).lower() == "ec":
                    try:
                        plant_threshold = float(value)
                    except (ValueError, TypeError):
                        _LOGGER.error("Invalid EC threshold value for plant %s: %s", plant_id, value)
                        plant_threshold = None
                    break

        # Get current EC sensor state
        state = self._hass.states.get(ec_entity)
        if not state or state.state in ("unknown", "unavailable"):
            _LOGGER.warning(
                "EC sensor %s is unavailable or has no data; skipping EC trend analysis for plant %s.",
                ec_entity,
                plant_id,
            )
            return
        try:
            current_val = float(state.state)
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Current state of %s is not numeric (%s); cannot analyze EC trends for plant %s.",
                ec_entity,
                state.state,
                plant_id,
            )
            return

        # Determine time window bounds
        now = datetime.now(UTC)
        start_sudden = now - timedelta(hours=SUDDEN_CHANGE_WINDOW_HOURS)
        start_sustained = now - timedelta(hours=SUSTAINED_HIGH_WINDOW_HOURS)

        # Query state history for the EC sensor
        try:
            history_sudden = state_changes_during_period(
                self._hass, start_sudden, now, entity_id=ec_entity, include_start_time_state=True
            )
            history_sustained = state_changes_during_period(
                self._hass, start_sustained, now, entity_id=ec_entity, include_start_time_state=True
            )
        except Exception as e:
            _LOGGER.error("Failed to retrieve history for %s: %s", ec_entity, e)
            return

        states_sudden = history_sudden.get(ec_entity.lower(), []) if isinstance(history_sudden, dict) else []
        states_sustained = history_sustained.get(ec_entity.lower(), []) if isinstance(history_sustained, dict) else []

        # Extract numeric EC values from history, filtering out invalid states
        ec_values_sudden: list[float] = []
        for s in states_sudden:
            # Each state in history is a homeassistant.core.State object
            if not hasattr(s, "state"):
                continue
            if s.state in ("unknown", "unavailable"):
                continue
            try:
                val = float(s.state)
                ec_values_sudden.append(val)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Non-numeric EC state encountered for %s in sudden window: %s",
                    ec_entity,
                    s.state,
                )
        ec_values_sustained: list[float] = []
        for s in states_sustained:
            if not hasattr(s, "state"):
                continue
            if s.state in ("unknown", "unavailable"):
                continue
            try:
                val = float(s.state)
                ec_values_sustained.append(val)
            except (ValueError, TypeError):
                _LOGGER.warning(
                    "Non-numeric EC state encountered for %s in sustained window: %s",
                    ec_entity,
                    s.state,
                )

        if not ec_values_sudden or not ec_values_sustained:
            # If there's no data in history (unlikely if current_val exists), skip
            _LOGGER.warning(
                "No EC history data available for plant %s (sensor %s); skipping trend analysis.",
                plant_id,
                ec_entity,
            )
            return

        # Initialize list for new alerts to record
        new_alerts: list[dict] = []

        # Check for sudden EC increase over the defined window
        # Compare EC at start of window vs end (current) to detect a large rise
        first_val = ec_values_sudden[0]  # state at ~start of sudden window
        last_val = ec_values_sudden[-1] if ec_values_sudden else current_val
        # Compute net change over the sudden window
        if last_val - first_val > SUDDEN_CHANGE_THRESHOLD:
            delta = last_val - first_val
            alert_entry = {
                "timestamp": now.isoformat(),
                "type": "sudden_increase",
                "change": round(delta, 2),
                "window_hours": SUDDEN_CHANGE_WINDOW_HOURS,
                "start_value": round(first_val, 2),
                "end_value": round(last_val, 2),
            }
            new_alerts.append(alert_entry)
            _LOGGER.warning(
                "Sudden EC increase detected for plant %s: EC rose by %.2f mS/cm in the last %d hours (%.2f -> %.2f).",
                plant_id,
                delta,
                SUDDEN_CHANGE_WINDOW_HOURS,
                first_val,
                last_val,
            )

        # Check for sustained high EC above threshold if threshold is known
        if plant_threshold is not None and ec_values_sustained:
            min_val = min(ec_values_sustained)
            if min_val > plant_threshold:
                # All readings in the sustained window were above the threshold
                alert_entry = {
                    "timestamp": now.isoformat(),
                    "type": "high_ec",
                    "threshold": round(plant_threshold, 2),
                    "min_value": round(min_val, 2),
                    "window_hours": SUSTAINED_HIGH_WINDOW_HOURS,
                }
                new_alerts.append(alert_entry)
                _LOGGER.warning(
                    "Sustained high EC for plant %s: EC has been above %.2f mS/cm "
                    "for at least %d hours (minimum %.2f).",
                    plant_id,
                    plant_threshold,
                    SUSTAINED_HIGH_WINDOW_HOURS,
                    min_val,
                )

        # If any alerts were generated, save them to the alerts log
        if new_alerts:
            # Ensure the plant has an entry in the alerts log
            if plant_id not in self._alerts:
                self._alerts[plant_id] = []
            # Append new alerts
            self._alerts[plant_id].extend(new_alerts)
            # Persist to file
            self._save_to_file()

    def _save_to_file(self) -> None:
        """Save the current EC alerts log to the JSON file."""
        os.makedirs(os.path.dirname(self._data_file) or ".", exist_ok=True)
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(self._alerts, f, indent=2)
        except Exception as e:
            _LOGGER.error("Failed to write EC alerts log to %s: %s", self._data_file, e)
