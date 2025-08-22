from typing import Dict, List

from .utils import lazy_dataset, normalize_key, list_dataset_entries

DATA_FILE = "companions/companion_plants.json"
_data = lazy_dataset(DATA_FILE)

__all__ = [
    "list_supported_plants",
    "get_companion_info",
    "recommend_companions",
    "recommend_antagonists",
]


def list_supported_plants() -> List[str]:
    """Return plant types with companion planting info."""
    return list_dataset_entries(_data())


def get_companion_info(plant_type: str) -> Dict[str, List[str]]:
    """Return companion planting data for ``plant_type``."""
    return _data().get(normalize_key(plant_type), {})


def recommend_companions(plant_type: str) -> List[str]:
    """Return recommended companion plants for ``plant_type``."""
    return get_companion_info(plant_type).get("companions", [])


def recommend_antagonists(plant_type: str) -> List[str]:
    """Return plants to avoid near ``plant_type``."""
    return get_companion_info(plant_type).get("antagonists", [])
