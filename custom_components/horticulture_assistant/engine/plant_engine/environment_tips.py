"""Access to general environment management tips."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict

from .utils import (
    lazy_dataset,
    list_dataset_entries,
    normalize_key,
    clear_dataset_cache,
)

DATA_FILE = "environment/environment_tips.yaml"

# Lazy loader so importing this module has minimal overhead
_DATA = lazy_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_environment_tips",
    "refresh_cache",
]


def list_supported_plants() -> list[str]:
    """Return plant types with environment tips defined."""
    return list_dataset_entries(_DATA())


@lru_cache(maxsize=None)
def get_environment_tips(plant_type: str, stage: str | None = None) -> Dict[str, str]:
    """Return environment management tips for ``plant_type`` and ``stage``.

    The dataset may include a ``default`` section with general tips and optional
    stage-specific mappings. Stage entries override any defaults. If no tips are
    defined for the plant or stage an empty dictionary is returned.
    """

    plant = _DATA().get(normalize_key(plant_type))
    if not isinstance(plant, dict):
        return {}

    tips: Dict[str, str] = {}

    default = plant.get("default")
    if isinstance(default, dict):
        for k, v in default.items():
            if isinstance(v, str):
                tips[k] = v
    else:
        # backward compatibility with old dataset structure where tips were
        # stored directly under the plant mapping
        for k, v in plant.items():
            if isinstance(v, str):
                tips[k] = v

    if stage:
        stage_tips = plant.get(normalize_key(stage))
        if isinstance(stage_tips, dict):
            for k, v in stage_tips.items():
                if isinstance(v, str):
                    tips[k] = v

    return tips


def refresh_cache() -> None:
    """Clear cached dataset values."""
    clear_dataset_cache()
    _DATA.cache_clear()
    get_environment_tips.cache_clear()
