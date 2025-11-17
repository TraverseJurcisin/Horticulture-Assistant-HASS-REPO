import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def generate_stress_profiles(plant_id: str, base_path: str = None, overwrite: bool = False) -> str:
    """Generate or update pest resistance and stress tolerance profiles for a plant.

    This scaffolds `pest_resistance.json` and `stress_tolerance.json` in
    `plants/<plant_id>/`, populating predefined keys for pest resistance and
    stress tolerance with ``None`` defaults.

    If a file already exists and ``overwrite`` is False, the file is left
    unchanged. If ``overwrite`` is True or the file is missing, a new file is
    created (or an existing file is overwritten) with the default structure. All
    actions (creation, skipping, overwriting) are logged for clarity.

    :param plant_id: Identifier for the plant (used as directory name under the
        base path).
    :param base_path: Optional base directory path for plant profiles (defaults
        to "plants/" in the current working directory).
    :param overwrite: If True, overwrite existing files; if False, skip writing
        if files already exist.
    :return: The plant_id if profiles were successfully generated (or already
        present without changes), or an empty string on error (for example, if
        directory creation fails).
    """

    # Define default content for pest_resistance.json
    pest_resistance_data = {
        "known_pests": None,
        "pest_pressure_by_stage": None,
        "symptoms": None,
        "resistance_mechanisms": None,
        "pesticide_sensitivity": None,
        "pest_location_targeting": None,
    }

    # Define default content for stress_tolerance.json
    stress_tolerance_data = {
        "drought": None,
        "salinity": None,
        "temperature_extremes": None,
        "compaction": None,
        "wind": None,
        "flooding": None,
        "frost": None,
        "pruning": None,
        "heavy_metal_tolerance": None,
    }

    profile_sections = {
        "pest_resistance.json": pest_resistance_data,
        "stress_tolerance.json": stress_tolerance_data,
    }

    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
