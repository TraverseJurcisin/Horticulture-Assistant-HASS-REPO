import logging
import json
import os

_LOGGER = logging.getLogger(__name__)

def scaffold_profile_files(plant_id: str, base_path: str = None, overwrite: bool = False):
    """
    Create introduction.json and identification.json files for a given plant profile with default fields.
    If base_path is provided, use that as base directory; otherwise, default to a "plants" directory in current working path.
    If overwrite is False, existing files will not be modified.
    Logs all actions (directory creation, file writing, skipping, errors).
    :param plant_id: Identifier for the plant (used as directory name under base_path).
    :param base_path: Base directory where the 'plants' folder is located (optional).
    :param overwrite: Whether to overwrite existing files if they exist.
    :return: List of files created or overwritten. Returns None if an error prevents file creation.
    """
    # Determine base directory for plant profiles
    base_dir = base_path if base_path is not None else os.path.join(os.getcwd(), "plants")
    plant_dir = os.path.join(base_dir, str(plant_id))
    # Log starting action
    _LOGGER.info("Scaffolding profile files for plant '%s' in directory: %s (overwrite=%s)", plant_id, plant_dir, overwrite)
    # Ensure the plant directory exists
    if not os.path.isdir(plant_dir):
        try:
            os.makedirs(plant_dir, exist_ok=True)
            _LOGGER.info("Created plant directory: %s", plant_dir)
        except Exception as e:
            _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
            return None
    else:
        _LOGGER.info("Plant directory already exists: %s", plant_dir)
    # Default profile content for introduction and identification
    introduction_data = {
        "primary_uses": None,
        "duration": None,
        "growth_habit": None,
        "key_features": None,
        "deciduous_or_evergreen": None,
        "history": None,
        "native_regions": None,
        "domestication": None,
        "cultural_significance": None,
        "legal_restrictions": None,
        "etymology": None,
        "cautions": None
    }
    identification_data = {
        "general_description": None,
        "leaf_structure": None,
        "adaptations": None,
        "rooting": None,
        "storm_resistance": None,
        "self_pruning": None,
        "growth_rates": None,
        "dimensions": None,
        "phylogeny": None,
        "defenses": None,
        "ecological_interactions": None
    }
    # File paths
    intro_path = os.path.join(plant_dir, "introduction.json")
    ident_path = os.path.join(plant_dir, "identification.json")
    created_or_updated = []
    # Handle introduction.json
    if os.path.exists(intro_path):
        if overwrite:
            try:
                with open(intro_path, 'w', encoding='utf-8') as f:
                    json.dump(introduction_data, f, ensure_ascii=False, indent=4)
                _LOGGER.info("Overwrote existing introduction.json for plant '%s'", plant_id)
                created_or_updated.append("introduction.json")
            except Exception as e:
                _LOGGER.error("Failed to write introduction.json for plant '%s': %s", plant_id, e)
        else:
            _LOGGER.info("introduction.json already exists for plant '%s'; skipping (overwrite=False)", plant_id)
    else:
        try:
            with open(intro_path, 'w', encoding='utf-8') as f:
                json.dump(introduction_data, f, ensure_ascii=False, indent=4)
            _LOGGER.info("Created introduction.json for plant '%s'", plant_id)
            created_or_updated.append("introduction.json")
        except Exception as e:
            _LOGGER.error("Failed to write introduction.json for plant '%s': %s", plant_id, e)
    # Handle identification.json
    if os.path.exists(ident_path):
        if overwrite:
            try:
                with open(ident_path, 'w', encoding='utf-8') as f:
                    json.dump(identification_data, f, ensure_ascii=False, indent=4)
                _LOGGER.info("Overwrote existing identification.json for plant '%s'", plant_id)
                created_or_updated.append("identification.json")
            except Exception as e:
                _LOGGER.error("Failed to write identification.json for plant '%s': %s", plant_id, e)
        else:
            _LOGGER.info("identification.json already exists for plant '%s'; skipping (overwrite=False)", plant_id)
    else:
        try:
            with open(ident_path, 'w', encoding='utf-8') as f:
                json.dump(identification_data, f, ensure_ascii=False, indent=4)
            _LOGGER.info("Created identification.json for plant '%s'", plant_id)
            created_or_updated.append("identification.json")
        except Exception as e:
            _LOGGER.error("Failed to write identification.json for plant '%s': %s", plant_id, e)
    return created_or_updated