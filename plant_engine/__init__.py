"""Plant engine package utilities."""

from .utils import load_json, save_json
from .environment_manager import get_environmental_targets
from .pest_manager import get_pest_guidelines
from .fertigation import recommend_fertigation_schedule

# Run functions should be imported explicitly to avoid heavy imports at package
# initialization time.
__all__ = [
    "load_json",
    "save_json",
    "get_environmental_targets",
    "get_pest_guidelines",
    "recommend_fertigation_schedule",
]
