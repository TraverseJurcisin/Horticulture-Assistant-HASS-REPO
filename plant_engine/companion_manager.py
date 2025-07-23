"""Companion planting guidelines access helpers."""
from __future__ import annotations

from typing import Dict, List

from .utils import load_dataset, normalize_key

DATA_FILE = "companion_plant_guidelines.json"

# dataset loaded at import for efficiency
_DATA: Dict[str, Dict[str, List[str]]] = load_dataset(DATA_FILE)


def list_supported_plants() -> List[str]:
    """Return all plants with companion guidelines."""
    return sorted(_DATA.keys())


def get_companion_guidelines(plant_type: str) -> Dict[str, List[str]]:
    """Return companion and antagonist lists for ``plant_type``."""
    return _DATA.get(normalize_key(plant_type), {})


def list_companions(plant_type: str) -> List[str]:
    """Return recommended companion plants for ``plant_type``."""
    return get_companion_guidelines(plant_type).get("companions", [])


def list_antagonists(plant_type: str) -> List[str]:
    """Return plants that should be avoided near ``plant_type``."""
    return get_companion_guidelines(plant_type).get("antagonists", [])


__all__ = [
    "list_supported_plants",
    "get_companion_guidelines",
    "list_companions",
    "list_antagonists",
]
