# File: custom_components/horticulture_assistant/utils/profile_regulatory_writer.py

import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False) -> None:
    """Create regulatory.json and export_profile.json for a given plant's profile directory.
    
    This scaffolds a directory under the base_path (defaults to "plants") named after the plant_id,
    and creates two JSON files within it: "regulatory.json" and "export_profile.json".
    Each file contains preset fields relevant to plant regulatory compliance and export profiles, initialized to null values.
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
    
    # Define default structures for regulatory and export profile
    regulatory_data = {
        "propagation_laws": None,
        "local_restrictions": None,
        "state_restrictions": None,
        "national_restrictions": None,
        "seed_labeling_requirements": None,
        "intellectual_property_claims": None,
        "banned_substances": None,
        "ethical_sourcing": None
    }
    export_profile_data = {
        "exportable_forms": None,
        "phytosanitary_certificates": None,
        "fumigation_status": None,
        "customs_codes": None,
        "known_trade_restrictions": None,
        "preferred_international_markets": None,
        "country_specific_demand": None
    }
    
    # File paths
    reg_file = os.path.join(plant_dir, "regulatory.json")
    export_file = os.path.join(plant_dir, "export_profile.json")
    
    # Write or skip regulatory.json
    if not overwrite and os.path.isfile(reg_file):
        _LOGGER.info("Regulatory file already exists at %s; skipping (overwrite=False).", reg_file)
    else:
        try:
            with open(reg_file, "w", encoding="utf-8") as f:
                json.dump(regulatory_data, f, indent=2)
            _LOGGER.info("Regulatory profile created for plant %s at %s", plant_id, reg_file)
        except Exception as e:
            _LOGGER.error("Failed to write regulatory profile for plant %s: %s", plant_id, e)
    
    # Write or skip export_profile.json
    if not overwrite and os.path.isfile(export_file):
        _LOGGER.info("Export profile file already exists at %s; skipping (overwrite=False).", export_file)
    else:
        try:
            with open(export_file, "w", encoding="utf-8") as f:
                json.dump(export_profile_data, f, indent=2)
            _LOGGER.info("Export profile created for plant %s at %s", plant_id, export_file)
        except Exception as e:
            _LOGGER.error("Failed to write export profile for plant %s: %s", plant_id, e)