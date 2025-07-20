import os
import json
import logging
from pathlib import Path

try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None  # Allow usage outside Home Assistant for testing

_LOGGER = logging.getLogger(__name__)

def initialize_nutrient_logs(plant_id: str, hass: 'HomeAssistant' = None, base_dir: str = None, overwrite: bool = False) -> bool:
    """
    Initialize nutrient log files for a given plant profile.
    
    This creates two JSON log files under plants/<plant_id>/ if they do not exist (or if overwrite is True):
      - nutrient_application_log.json: an empty list; each future entry to include keys like 
        "timestamp", "product_name", "nutrient_formulation", "rate_applied_ml", 
        "delivery_method", "zone_targeted", "application_success", and "notes".
      - fertilizer_cost_tracking.json: an empty list; each entry to include keys like 
        "product_name", "unit_cost", "unit_type", "purchase_date", "vendor", 
        "batch_id", "expiration_date", and "notes".
    
    If files already exist and overwrite is False, they are left untouched.
    If overwrite is True, existing files are cleared (overwritten with an empty list structure).
    
    Logs file creations, skips (with entry count if applicable), and any errors encountered.
    
    :param plant_id: Identifier of the plant (also directory name under base path).
    :param hass: HomeAssistant instance (optional) for path resolution.
    :param base_dir: Base directory containing plant profile folders (defaults to "plants/" in current working directory or Home Assistant config).
    :param overwrite: If True, overwrite existing log files; if False, skip creating files that already exist.
    :return: True if operation succeeded (or files skipped) without errors, False if an error occurred.
    """
    # Determine base directory for plant logs
    if base_dir:
        base_path = Path(base_dir)
    elif hass is not None:
        try:
            base_path = Path(hass.config.path("plants"))
        except Exception as e:
            _LOGGER.error("Error resolving Home Assistant plants directory: %s", e)
            base_path = Path("plants")
    else:
        base_path = Path("plants")
    
    plant_dir = base_path / plant_id
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
        return False
    
    log_files = ["nutrient_application_log.json", "fertilizer_cost_tracking.json"]
    success = True
    for filename in log_files:
        file_path = plant_dir / filename
        if file_path.exists() and not overwrite:
            # Skip creation if file already exists and not overwriting
            entry_count = None
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        entry_count = len(data)
            except Exception as e:
                _LOGGER.warning("Could not read %s to count entries: %s", file_path, e)
            if entry_count is not None:
                _LOGGER.info("File %s already exists with %d entries. Skipping creation.", file_path, entry_count)
            else:
                _LOGGER.info("File %s already exists. Skipping creation.", file_path)
            continue
        
        # Create or overwrite the file with an empty list
        existed_before = file_path.exists()
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump([], f, indent=2)
            if existed_before and overwrite:
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
        except Exception as e:
            _LOGGER.error("Failed to write %s: %s", file_path, e)
            success = False
    return success