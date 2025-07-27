# File: custom_components/horticulture_assistant/utils/nutrient_use_efficiency.py
"""Utility for logging fertilizer use and computing nutrient efficiency.

The :class:`NutrientUseEfficiency` helper keeps track of all fertilizer
applications for individual plants and aggregates yield data from the default
``data/yield_logs.json`` file.  It is intentionally decoupled from Home
Assistant so the calculations can be unit tested in isolation.  Usage logs are
stored in JSON for easy inspection and further analysis.
"""
import os
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Union

from custom_components.horticulture_assistant.utils.path_utils import (
    config_path,
    data_path,
)
from plant_engine.utils import load_dataset

try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None  # Allow usage outside Home Assistant for testing

_LOGGER = logging.getLogger(__name__)

TARGETS_FILE = "nutrient_use_efficiency_targets.json"
_NUE_TARGETS: Dict[str, Dict[str, float]] = load_dataset(TARGETS_FILE)

class NutrientUseEfficiency:
    """Track fertilizer usage and calculate nutrient use efficiency."""

    def __init__(self, data_file: Optional[str] = None, hass: Optional['HomeAssistant'] = None) -> None:
        """Load existing logs or initialize empty structures.

        Parameters
        ----------
        data_file : str, optional
            Path to the nutrient log file.  Defaults to ``data/nutrient_use.json``.
        hass : HomeAssistant, optional
            Used only for resolving paths when running inside Home Assistant.
        """
        # Determine the data file path
        if data_file is None:
            data_file = data_path(hass, "nutrient_use.json")
        self._data_file = data_file
        self._hass = hass
        # Internal logs
        self._usage_logs: Dict[str, List[Dict]] = {}
        self.application_log: Dict[str, Dict[str, float]] = {}
        self.tissue_log: Dict[str, Dict[str, float]] = {}
        self.yield_log: Dict[str, float] = {}
        # Load existing usage logs from file if available
        try:
            with open(self._data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for pid, entries in data.items():
                    if isinstance(entries, list):
                        self._usage_logs[pid] = entries
                    else:
                        _LOGGER.warning("Nutrient use log for plant %s is not a list; resetting to empty list.", pid)
                        self._usage_logs[pid] = []
            else:
                _LOGGER.warning("Nutrient use log file format invalid (expected dict at top level); starting with empty log.")
        except FileNotFoundError:
            _LOGGER.info("Nutrient use log file not found at %s; starting new nutrient use log.", self._data_file)
        except json.JSONDecodeError as e:
            _LOGGER.error("JSON decode error reading nutrient use log from %s: %s; initializing empty log.", self._data_file, e)
        except Exception as e:
            _LOGGER.error("Error loading nutrient use log from %s: %s; initializing empty log.", self._data_file, e)
        # Build application_log totals from loaded records
        for pid, entries in self._usage_logs.items():
            total_nutrients: Dict[str, float] = {}
            for record in entries:
                nutrients = record.get("nutrients", {})
                for nutrient, amt in nutrients.items():
                    try:
                        amt_val = float(amt)
                    except (ValueError, TypeError):
                        _LOGGER.warning("Invalid nutrient amount '%s' for %s in plant %s log; skipping.", amt, nutrient, pid)
                        continue
                    total_nutrients[nutrient] = total_nutrients.get(nutrient, 0.0) + amt_val
            self.application_log[pid] = total_nutrients
        # Load existing yield totals from yield tracker logs if available
        try:
            yield_file = data_path(hass, "yield_logs.json")
        except Exception:
            yield_file = data_path(None, "yield_logs.json")
        try:
            with open(yield_file, "r", encoding="utf-8") as yf:
                yield_data = json.load(yf)
            if isinstance(yield_data, dict):
                for pid, entries in yield_data.items():
                    if isinstance(entries, list):
                        total_yield = 0.0
                        for entry in entries:
                            if isinstance(entry, dict):
                                try:
                                    w = float(entry.get("weight", 0.0))
                                except (ValueError, TypeError):
                                    w = 0.0
                                total_yield += w
                        self.yield_log[pid] = total_yield
                    else:
                        _LOGGER.warning("Yield log for plant %s is not a list; skipping yield load for this plant.", pid)
            else:
                _LOGGER.warning("Yield logs file format invalid (expected dict at top level); yield data not loaded.")
        except FileNotFoundError:
            _LOGGER.info("Yield logs file not found at %s; proceeding without initial yield data.", yield_file)
        except json.JSONDecodeError as e:
            _LOGGER.error("JSON decode error reading yield logs from %s: %s; yield data not loaded.", yield_file, e)
        except Exception as e:
            _LOGGER.error("Error loading yield logs from %s: %s; yield data not loaded.", yield_file, e)

    @staticmethod
    def _format_date(value: Optional[Union[str, date, datetime]]) -> str:
        """Return ``YYYY-MM-DD`` string for ``value`` or today if ``None``."""
        if value is None:
            return datetime.now().strftime("%Y-%m-%d")
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        return str(value)

    def log_fertilizer_application(self, plant_id: str, nutrient_mass: Dict[str, float],
                                   entry_date: Optional[Union[str, date, datetime]] = None,
                                   stage: Optional[str] = None) -> None:
        """
        Record a fertilizer application event for a plant.
        :param plant_id: Identifier of the plant.
        :param nutrient_mass: Dict of nutrient amounts applied (in mg), e.g. {"N": 150.0, "P": 50.0}.
        :param entry_date: Date of application (string 'YYYY-MM-DD', datetime/date object). Defaults to today if None.
        :param stage: Lifecycle stage of the plant at time of application (optional).
        """
        date_str = self._format_date(entry_date)
        # Determine stage name
        stage_name = stage
        if stage_name is None:
            # Try to retrieve current stage from plant registry if available
            reg_path = config_path(self._hass, "plant_registry.json") if self._hass is not None else "plant_registry.json"
            try:
                with open(reg_path, "r", encoding="utf-8") as rf:
                    reg_data = json.load(rf)
                if plant_id in reg_data:
                    stage_name = reg_data[plant_id].get("current_lifecycle_stage") or reg_data[plant_id].get("lifecycle_stage")
            except Exception:
                stage_name = None
        if stage_name is None:
            stage_name = "unknown"
        # Convert nutrient amounts to float and validate
        nutrient_mass_clean: Dict[str, float] = {}
        for nut, amt in nutrient_mass.items():
            try:
                amt_val = float(amt)
            except (ValueError, TypeError):
                _LOGGER.error("Invalid nutrient amount for %s in plant %s: %s", nut, plant_id, amt)
                return
            nutrient_mass_clean[nut] = amt_val
        # Create entry
        entry = {"date": date_str, "nutrients": nutrient_mass_clean, "stage": stage_name}
        # Append entry to logs and maintain chronological order
        if plant_id not in self._usage_logs:
            self._usage_logs[plant_id] = []
        self._usage_logs[plant_id].append(entry)
        try:
            self._usage_logs[plant_id].sort(key=lambda x: x.get("date", ""))
        except Exception as e:
            _LOGGER.warning("Failed to sort nutrient entries for plant %s: %s", plant_id, e)
        # Update running total for each nutrient
        if plant_id not in self.application_log:
            self.application_log[plant_id] = {}
        for nut, amt_val in nutrient_mass_clean.items():
            self.application_log[plant_id][nut] = self.application_log[plant_id].get(nut, 0.0) + amt_val
        # Persist to file
        self._save_to_file()
        _LOGGER.info("Fertilizer application logged for plant %s: %s on %s (stage: %s)", 
                     plant_id, nutrient_mass_clean, date_str, stage_name)

    def log_tissue_test(self, plant_id: str, tissue_nutrient_mass: Dict[str, float]) -> None:
        """
        Record a tissue nutrient analysis result for a given plant.
        Example: {"N": 9.2, "P": 2.3, "K": 7.4} (concentrations or content in % or mg as appropriate)
        """
        self.tissue_log[plant_id] = tissue_nutrient_mass
        _LOGGER.info("Tissue test recorded for plant %s: %s", plant_id, tissue_nutrient_mass)

    def log_yield(self, plant_id: str, yield_mass: Union[int, float], 
                  entry_date: Optional[Union[str, date, datetime]] = None) -> None:
        """
        Record a yield event (harvest) for a given plant.
        :param plant_id: Identifier of the plant.
        :param yield_mass: Yield amount in grams.
        :param entry_date: Date of yield (string 'YYYY-MM-DD', datetime/date object). Defaults to today if None.
        """
        date_str = self._format_date(entry_date)
        # Convert yield mass to float
        try:
            yield_val = float(yield_mass)
        except (ValueError, TypeError):
            _LOGGER.error("Invalid yield mass value for plant %s: %s", plant_id, yield_mass)
            return
        # Update total yield for plant
        if plant_id not in self.yield_log:
            self.yield_log[plant_id] = 0.0
        self.yield_log[plant_id] += yield_val
        _LOGGER.info("Yield logged for plant %s: %.2f g on %s", plant_id, yield_val, date_str)

    def compute_efficiency(self, plant_id: str) -> Optional[Dict[str, float]]:
        """
        Calculate nutrient use efficiency for the given plant.
        Efficiency is defined as grams of yield produced per mg of nutrient applied.
        Returns a dict mapping each nutrient to its efficiency value, or None if data is incomplete.
        """
        if plant_id not in self.application_log or plant_id not in self.yield_log:
            _LOGGER.warning("Cannot compute efficiency for plant %s: missing data (applied nutrients or yield).", plant_id)
            return None
        total_yield_g = self.yield_log.get(plant_id, 0.0)
        if total_yield_g <= 0:
            _LOGGER.warning("No yield recorded for plant %s; efficiency cannot be computed.", plant_id)
            return None
        applied_totals = self.application_log.get(plant_id, {})
        results: Dict[str, float] = {}
        for nutrient, total_mg in applied_totals.items():
            if total_mg <= 0:
                continue
            # Efficiency: grams of yield per mg of this nutrient
            efficiency_value = total_yield_g / total_mg
            results[nutrient] = round(efficiency_value, 4)
        return results

    def total_nutrients_applied(self, plant_id: str) -> Dict[str, float]:
        """Return cumulative nutrient mass (mg) applied to ``plant_id``."""
        return self.application_log.get(plant_id, {}).copy()

    def compute_overall_efficiency(self) -> Dict[str, Dict[str, float]]:
        """Return nutrient efficiency values for all plants with data."""
        output: Dict[str, Dict[str, float]] = {}
        for pid in self.application_log:
            eff = self.compute_efficiency(pid)
            if eff:
                output[pid] = eff
        return output

    def efficiency_targets(self, plant_type: str) -> Dict[str, float]:
        """Return NUE targets for ``plant_type`` from bundled datasets."""

        data = _NUE_TARGETS.get(str(plant_type).lower(), {})
        targets: Dict[str, float] = {}
        for nut, val in data.items():
            try:
                targets[nut] = float(val)
            except (TypeError, ValueError):
                continue
        return targets

    def compare_to_targets(self, plant_id: str, plant_type: str) -> Dict[str, float]:
        """Return difference between measured NUE and target values."""

        eff = self.compute_efficiency(plant_id)
        if eff is None:
            return {}
        targets = self.efficiency_targets(plant_type)
        comparison: Dict[str, float] = {}
        for nut, value in eff.items():
            target = targets.get(nut)
            if target is not None:
                comparison[nut] = round(value - target, 2)
        return comparison

    def get_usage_summary(self, plant_id: str, by: str) -> Dict[str, Dict[str, float]]:
        """
        Summarize nutrient usage for a plant, grouped by a time period or lifecycle stage.
        :param plant_id: Identifier of the plant.
        :param by: Grouping method - "week", "month", or "stage".
        :return: Dictionary where keys are period identifiers (week number, month, or stage name),
                 and values are dicts of total nutrient applied in that period.
        """
        group_by = str(by).lower()
        if plant_id not in self._usage_logs or not self._usage_logs[plant_id]:
            return {}
        summary: Dict[str, Dict[str, float]] = {}
        for entry in self._usage_logs[plant_id]:
            date_str = entry.get("date")
            # Parse date string to date object for grouping
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception as e:
                _LOGGER.warning("Invalid date format '%s' in logs for plant %s: %s", date_str, plant_id, e)
                continue
            if group_by == "week":
                year, week_num, _ = entry_date.isocalendar()
                key = f"{year}-W{week_num:02d}"
            elif group_by == "month":
                key = f"{entry_date.year}-{entry_date.month:02d}"
            elif group_by == "stage":
                key = entry.get("stage", "unknown")
            else:
                raise ValueError(f"Invalid summary grouping: {by}. Use 'week', 'month', or 'stage'.")
            # Aggregate nutrient amounts
            if key not in summary:
                summary[key] = {}
            for nut, amt in entry.get("nutrients", {}).items():
                try:
                    amt_val = float(amt)
                except (ValueError, TypeError):
                    amt_val = 0.0
                summary[key][nut] = summary[key].get(nut, 0.0) + amt_val
        return summary

    def _save_to_file(self) -> None:
        """Persist usage logs to ``self._data_file``."""
        os.makedirs(os.path.dirname(self._data_file) or ".", exist_ok=True)
        try:
            with open(self._data_file, "w", encoding="utf-8") as f:
                json.dump(self._usage_logs, f, indent=2)
        except Exception as e:
            _LOGGER.error(
                "Failed to write nutrient use logs to %s: %s", self._data_file, e
            )

