from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, Tuple, List

from .utils import load_dataset, normalize_key

DATA_FILE = "fertilizers/fertilizer_ingredients.json"


@dataclass(frozen=True, slots=True)
class IngredientProfile:
    """Profile describing a fertilizer ingredient."""

    name: str
    nutrient_content: Dict[str, float]
    chemical_formula: str | None = None
    form: str | None = None
    aliases: Tuple[str, ...] = ()


@lru_cache(maxsize=None)
def _load_profiles() -> Tuple[Dict[str, IngredientProfile], Dict[str, str]]:
    data = load_dataset(DATA_FILE)
    profiles: Dict[str, IngredientProfile] = {}
    alias_map: Dict[str, str] = {}
    for name, info in data.items():
        canonical = normalize_key(name)
        nutrient_content = {
            k: float(v) for k, v in info.get("nutrient_content", {}).items()
        }
        aliases = tuple(info.get("aliases", []))
        profiles[canonical] = IngredientProfile(
            name=canonical,
            nutrient_content=nutrient_content,
            chemical_formula=info.get("chemical_formula"),
            form=info.get("form"),
            aliases=aliases,
        )
        for alias in aliases:
            alias_map[normalize_key(alias)] = canonical
    return profiles, alias_map


def get_ingredient_profile(name: str) -> IngredientProfile | None:
    """Return :class:`IngredientProfile` for ``name`` or ``None`` if unknown."""

    profiles, alias_map = _load_profiles()
    key = normalize_key(name)
    canonical = alias_map.get(key, key)
    return profiles.get(canonical)


def list_ingredients() -> List[str]:
    """Return sorted canonical ingredient names."""

    profiles, _ = _load_profiles()
    return sorted(profiles.keys())


__all__ = ["IngredientProfile", "get_ingredient_profile", "list_ingredients"]
