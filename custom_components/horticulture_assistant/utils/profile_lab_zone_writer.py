import logging
from .profile_helpers import write_profile_sections

_LOGGER = logging.getLogger(__name__)


def generate_lab_zone_profiles(plant_id: str, base_path: str | None = None, overwrite: bool = False) -> str:
    """Create lab analysis log and zone calendar files for ``plant_id``."""
    zone_calendar = {
        f"{i}{suffix}": {
            "seeding_months": None,
            "transplant_months": None,
            "expected_harvest_months": None,
            "frost_risk_months": None,
            "critical_stress_windows": None,
        }
        for i in range(1, 14)
        for suffix in ("a", "b")
    }
    profile_sections = {
        "lab_analysis_log.json": [],
        "zone_calendar.json": zone_calendar,
    }
    return write_profile_sections(plant_id, profile_sections, base_path, overwrite)
