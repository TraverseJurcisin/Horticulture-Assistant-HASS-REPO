"""Plant engine package utilities."""

from .utils import load_json, save_json
from .environment_manager import get_environmental_targets, recommend_environment_adjustments
from .pest_manager import (
    get_pest_guidelines,
    recommend_treatments as recommend_pest_treatments,
)
from .disease_manager import (
    get_disease_guidelines,
    recommend_treatments as recommend_disease_treatments,
)
from .fertigation import recommend_fertigation_schedule, recommend_correction_schedule
from .rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
    RootZone,
)
from .nutrient_manager import calculate_deficiencies
from .growth_stage import get_stage_info

# Run functions should be imported explicitly to avoid heavy imports at package
# initialization time.
__all__ = [
    "load_json",
    "save_json",
    "get_environmental_targets",
    "recommend_environment_adjustments",
    "get_pest_guidelines",
    "recommend_pest_treatments",
    "get_disease_guidelines",
    "recommend_disease_treatments",
    "recommend_fertigation_schedule",
    "recommend_correction_schedule",
    "calculate_deficiencies",
    "get_stage_info",
    "estimate_rootzone_depth",
    "estimate_water_capacity",
    "RootZone",
]
