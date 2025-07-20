"""Plant engine package utilities."""

from .utils import load_json, save_json
from .environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
    list_supported_plants as list_environment_plants,
)
from .pest_manager import (
    get_pest_guidelines,
    recommend_treatments as recommend_pest_treatments,
    list_supported_plants as list_pest_plants,
)
from .disease_manager import (
    get_disease_guidelines,
    recommend_treatments as recommend_disease_treatments,
    list_supported_plants as list_disease_plants,
)
from .fertigation import (
    recommend_fertigation_schedule,
    recommend_correction_schedule,
    get_fertilizer_purity,
)
from .rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
    RootZone,
)
from .nutrient_manager import (
    calculate_deficiencies,
    list_supported_plants as list_nutrient_plants,
)
from .growth_stage import get_stage_info, list_growth_stages

# Run functions should be imported explicitly to avoid heavy imports at package
# initialization time.
__all__ = [
    "load_json",
    "save_json",
    "get_environmental_targets",
    "recommend_environment_adjustments",
    "list_environment_plants",
    "get_pest_guidelines",
    "recommend_pest_treatments",
    "list_pest_plants",
    "get_disease_guidelines",
    "recommend_disease_treatments",
    "list_disease_plants",
    "recommend_fertigation_schedule",
    "recommend_correction_schedule",
    "get_fertilizer_purity",
    "calculate_deficiencies",
    "list_nutrient_plants",
    "get_stage_info",
    "list_growth_stages",
    "estimate_rootzone_depth",
    "estimate_water_capacity",
    "RootZone",
]
