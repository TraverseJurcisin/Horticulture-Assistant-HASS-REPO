import logging

from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def scaffold_profile_files(
    plant_id: str, base_path: str | None = None, overwrite: bool = False
) -> str:
    """Create phenophase observation and developmental threshold profiles."""
    profile_sections = {
        "phenophase_observations.json": {
            "bud_break_date": None,
            "flowering_onset": None,
            "fruit_set_date": None,
            "first_harvest": None,
            "senescence_onset": None,
            "recorded_by": None,
            "notes": None,
        },
        "developmental_thresholds.json": {
            "gdd_required_per_stage": None,
            "photoperiod_triggers": None,
            "chill_hours_required": None,
            "stage_transition_factors": None,
            "nutrient_triggers": None,
            "vgi_thresholds": None,
        },
    }
    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
