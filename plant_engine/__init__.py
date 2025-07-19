"""Plant engine package utilities."""

from .utils import load_json, save_json
from .environment_manager import get_environmental_targets
from .pest_manager import get_pest_guidelines
from .fertigation import recommend_fertigation_schedule
from .nutrient_manager import calculate_deficiencies
from .growth_stage import get_stage_info

# Run functions should be imported explicitly to avoid heavy imports at package
# initialization time.
__all__ = [
    "load_json",
    "save_json",
    "get_environmental_targets",
    "get_pest_guidelines",
    "recommend_fertigation_schedule",
    "calculate_deficiencies",
    "get_stage_info",
]
