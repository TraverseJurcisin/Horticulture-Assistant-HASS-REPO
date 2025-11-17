# File: custom_components/horticulture_assistant/utils/yield_tracker.py
"""Utility for tracking and recording yield entries for plants."""

import json
import logging
import os
from datetime import date, datetime
from typing import Optional

from custom_components.horticulture_assistant.utils.path_utils import data_path

try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None  # Allow usage outside Home Assistant for testing

_LOGGER = logging.getLogger(__name__)


class YieldTracker:
    def __init__(self, data_file: str | None = None, hass: Optional['HomeAssistant'] = None):
        """
        Initialize the YieldTracker.
        Loads existing yield logs from the specified JSON file, or creates a new structure if file is absent.
        :param data_file: Path to the yield log JSON file. Defaults to 'data/yield_logs.json' in current directory.
        :param hass: HomeAssistant instance (optional) for firing events on updates.
        """
        # Determine the data file path
        if data_file is None:
            data_file = data_path(hass, "yield_logs.json")
        self._data_file = data_file
        self._hass = hass
        self._logs: dict[str, list[dict]] = {}
        # Load existing logs from file if available
        try:
            with open(self._data_file, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                # Ensure all keys map to list of entries
                for pid, entries in data.items():
                    if isinstance(entries, list):
                        self._logs[pid] = entries
                    else:
                        _LOGGER.warning("Yield log for plant %s is not a list; resetting to empty list.", pid)
                        self._logs[pid] = []
            else:
                _LOGGER.warning(
                    "Yield logs file format invalid (expected dict at top level); starting with empty logs."
                )
        except FileNotFoundError:
            _LOGGER.info("Yield logs file not found at %s; starting new yield log.", self._data_file)
        except json.JSONDecodeError as e:
            _LOGGER.error(
                "JSON decode error reading yield logs from %s: %s; initializing empty log.",
                self._data_file,
                e,
            )
        except Exception as e:
            _LOGGER.error("Error loading yield logs from %s: %s; initializing empty log.", self._data_file, e)

    def add_entry(
        self,
        plant_id: str,
        weight: int | float,
        entry_date: str | date | datetime | None = None,
        notes: str | None = None,
    ) -> None:
        """
        Add a new yield entry for a given plant.
        :param plant_id: Identifier of the plant.
        :param weight: Yield weight in grams.
        :param entry_date: Date of yield (string 'YYYY-MM-DD', or datetime/date object). Defaults to today if None.
        :param notes: Optional notes describing the yield entry.
        """
        # Determine date string
        if entry_date is None:
            # Use current date if not provided
            date_str = datetime.now().strftime("%Y-%m-%d")
        elif isinstance(entry_date, datetime):
            # Use date part of datetime
            date_str = entry_date.date().isoformat()
        elif isinstance(entry_date, date):
            date_str = entry_date.isoformat()
        else:
            # Assume it's a string already
            date_str = str(entry_date)
        # Convert weight to float for consistency
        try:
            weight_val = float(weight)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid weight value for yield entry: %s", weight)
            return
        # Create entry dict
        entry = {"date": date_str, "weight": weight_val}
        if notes:
            entry["notes"] = notes
        # Append entry to the plant's log
        if plant_id not in self._logs:
            self._logs[plant_id] = []
        self._logs[plant_id].append(entry)
        # Sort entries by date to maintain chronological order
        try:
            self._logs[plant_id].sort(key=lambda x: x.get("date", ""))
        except Exception as e:
            _LOGGER.warning("Failed to sort yield entries for plant %s: %s", plant_id, e)
        # Persist the updated logs to file
        self._save_to_file()
        _LOGGER.info("Yield entry added for plant %s: %.2f g on %s", plant_id, weight_val, date_str)
        # Fire an event to update sensors, if HomeAssistant is available
        if self._hass:
            try:
                from custom_components.horticulture_assistant.const import EVENT_YIELD_UPDATE

                total = self.get_total_yield(plant_id)
                self._hass.bus.fire(EVENT_YIELD_UPDATE, {"plant_id": plant_id, "yield": total})
                _LOGGER.debug(
                    "Fired event %s for plant %s with total yield %.2f g",
                    EVENT_YIELD_UPDATE,
                    plant_id,
                    total,
                )
            except Exception as e:
                _LOGGER.error("Error firing yield update event: %s", e)

    def get_total_yield(self, plant_id: str) -> float:
        """
        Calculate the total yield for a given plant.
        :param plant_id: Identifier of the plant.
        :return: Sum of all yield weights for the plant (in grams). Returns 0.0 if no entries.
        """
        entries = self._logs.get(plant_id, [])
        total = sum(entry.get("weight", 0.0) for entry in entries)
        return float(total)

    def get_average_yield(self, plant_id: str) -> float:
        """
        Calculate the average yield per entry for a given plant.
        :param plant_id: Identifier of the plant.
        :return: Average yield weight per entry (in grams). Returns 0.0 if no entries.
        """
        entries = self._logs.get(plant_id, [])
        count = len(entries)
        if count == 0:
            return 0.0
        total = sum(entry.get("weight", 0.0) for entry in entries)
        return float(total) / count

    def get_entries_for_plant(self, plant_id: str) -> list[dict]:
        """
        Retrieve all yield entries for the specified plant.
        :param plant_id: Identifier of the plant.
        :return: List of yield entry dicts for the plant. Each entry contains 'date', 'weight', and optional 'notes'.
        """
        return [entry.copy() for entry in self._logs.get(plant_id, [])]

    def get_entries_in_date_range(
        self,
        start_date: str | date | datetime,
        end_date: str | date | datetime,
        plant_id: str | None = None,
    ) -> list[dict]:
        """
        Retrieve yield entries within a date range (inclusive).
        :param start_date: Start of range (string 'YYYY-MM-DD' or date/datetime object).
        :param end_date: End of range (string 'YYYY-MM-DD' or date/datetime object).
        :param plant_id: If provided, filter entries only for this plant. If None, include all plants.
        :return: List of yield entry dicts within the range. If plant_id is None, each dict will include a 'plant_id'.
        """
        # Convert start_date and end_date to date objects for comparison
        if isinstance(start_date, datetime):
            start_dt = start_date.date()
        elif isinstance(start_date, date):
            start_dt = start_date
        else:
            try:
                start_dt = datetime.fromisoformat(str(start_date)).date()
            except Exception as e:
                _LOGGER.error("Invalid start_date '%s': %s", start_date, e)
                return []
        if isinstance(end_date, datetime):
            end_dt = end_date.date()
        elif isinstance(end_date, date):
            end_dt = end_date
        else:
            try:
                end_dt = datetime.fromisoformat(str(end_date)).date()
            except Exception as e:
                _LOGGER.error("Invalid end_date '%s': %s", end_date, e)
                return []
        if end_dt < start_dt:
            _LOGGER.warning("End date %s is earlier than start date %s; returning empty list.", end_dt, start_dt)
            return []
        results: list[dict] = []
        if plant_id:
            # Filter within specific plant
            for entry in self._logs.get(plant_id, []):
                try:
                    entry_date = datetime.fromisoformat(entry.get("date", "")).date()
                except Exception:
                    continue
                if start_dt <= entry_date <= end_dt:
                    results.append(entry.copy())
        else:
            # Search across all plants
            for pid, entries in self._logs.items():
                for entry in entries:
                    try:
                        entry_date = datetime.fromisoformat(entry.get("date", "")).date()
                    except Exception:
                        continue
                    if start_dt <= entry_date <= end_dt:
                        entry_copy = entry.copy()
                        entry_copy["plant_id"] = pid
                        results.append(entry_copy)
        # Sort results by date
        results.sort(key=lambda x: x.get("date", ""))
        return results

    def _save_to_file(self) -> None:
        """Save the current logs to the JSON file."""
        os.makedirs(os.path.dirname(self._data_file) or ".", exist_ok=True)
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(self._logs, f, indent=2)
        except Exception as e:
            _LOGGER.error("Failed to write yield logs to %s: %s", self._data_file, e)
