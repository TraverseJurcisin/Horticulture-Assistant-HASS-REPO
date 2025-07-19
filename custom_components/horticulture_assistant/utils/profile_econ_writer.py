# File: custom_components/horticulture_assistant/utils/profile_econ_writer.py

import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """Create economics.json and management.json for a given plant's profile directory.
    
    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "economics.json" and "management.json".
    Each file contains preset fields relevant to plant economics and management, initialized to null values.
    If a file already exists and overwrite is False, the file is left unchanged.
    Set overwrite=True to replace any existing files with the default structure.
    Logs messages for each created file, any skipped creations, and any errors encountered.
    """
    base_dir = base_path or "plants"
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Ensure the plant directory exists
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s for plant profile: %s", plant_dir, e)
        return
    
    # Define default structures for economics and management
    economics_data = {
        "labor_costs": None,
        "equipment_costs": None,
        "consumables": None,
        "production_expenses": None,
        "unit_economics": None,
        "market_value": None,
        "product_shelf_life": None,
        "transportation_and_logistics": None,
        "pricing_trends": None
    }
    management_data = {
        "recommended_cultivation_practices": None,
        "labor_cycles": None,
        "growth_stages_by_calendar": None,
        "harvest_strategies": None,
        "propagation_methods": None,
        "trellising_staking_spacing": None,
        "other_sops": None
    }
    
    # File paths
    econ_file = os.path.join(plant_dir, "economics.json")
    mgmt_file = os.path.join(plant_dir, "management.json")
    
    # Write or skip economics.json
    if not overwrite and os.path.isfile(econ_file):
        _LOGGER.info("Economics file already exists at %s; skipping (overwrite=False).", econ_file)
    else:
        try:
            with open(econ_file, "w", encoding="utf-8") as f:
                json.dump(economics_data, f, indent=2)
            _LOGGER.info("Economics profile created for plant %s at %s", plant_id, econ_file)
        except Exception as e:
            _LOGGER.error("Failed to write economics profile for plant %s: %s", plant_id, e)
    
    # Write or skip management.json
    if not overwrite and os.path.isfile(mgmt_file):
        _LOGGER.info("Management file already exists at %s; skipping (overwrite=False).", mgmt_file)
    else:
        try:
            with open(mgmt_file, "w", encoding="utf-8") as f:
                json.dump(management_data, f, indent=2)
            _LOGGER.info("Management profile created for plant %s at %s", plant_id, mgmt_file)
        except Exception as e:
            _LOGGER.error("Failed to write management profile for plant %s: %s", plant_id, e)