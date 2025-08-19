"""Species-based root cation exchange modeling utilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping

from plant_engine.utils import load_dataset

# Relative cation extraction multipliers for select species
SPECIES_CATION_FILE = "species/species_cation_profiles.json"
SPECIES_CATION_PROFILE: Dict[str, Mapping[str, float]] = load_dataset(SPECIES_CATION_FILE)


@dataclass
class MediaBuffer:
    """Simple representation of cation levels in the root zone."""

    Ca: float = 0.0
    K: float = 0.0
    Mg: float = 0.0
    S: float = 0.0

    def as_dict(self) -> Dict[str, float]:
        return {"Ca": self.Ca, "K": self.K, "Mg": self.Mg, "S": self.S}


def apply_species_demand(
    media: MediaBuffer,
    species: str,
    days: float = 1.0,
    base_daily_use: float = 1.0,
) -> MediaBuffer:
    """Return ``media`` after subtracting species cation demand."""

    profile = SPECIES_CATION_PROFILE.get(species.lower())
    if not profile:
        return media

    updated = MediaBuffer(**media.as_dict())
    for nutrient, factor in profile.items():
        if nutrient == "S_to_Ca":
            continue
        use = base_daily_use * factor * days
        current = getattr(updated, nutrient, 0.0)
        setattr(updated, nutrient, max(current - use, 0.0))

    ratio = profile.get("S_to_Ca")
    if ratio is not None and "Ca" in profile:
        try:
            ratio_val = float(ratio)
            ca_use = media.Ca - updated.Ca
            updated.S = max(updated.S - ca_use * ratio_val, 0.0)
        except (TypeError, ValueError):
            pass
    return updated


def recommend_amendments(
    media: MediaBuffer,
    species: str,
    thresholds: Mapping[str, float] | None = None,
) -> List[str]:
    """Return recommendation messages for depleted cations."""

    thresholds = thresholds or {}
    species_l = species.lower()
    messages: List[str] = []
    profile = SPECIES_CATION_PROFILE.get(species_l, {})

    def below(nutrient: str) -> bool:
        try:
            level = getattr(media, nutrient)
        except AttributeError:
            return False
        return level < float(thresholds.get(nutrient, 0.0))

    if species_l == "iris" and below("Mg"):
        messages.append(
            "Media in Iris zone depleted in Mg. Recommend gypsum + MgSO₄ amendment."
        )

    if species_l == "iris":
        ratio = profile.get("S_to_Ca")
        if ratio is not None:
            try:
                ratio_val = float(ratio)
                if media.Ca > 0 and media.S / media.Ca < ratio_val:
                    messages.append(
                        "S:Ca ratio below target for Iris. Add gypsum amendment."
                    )
            except (TypeError, ValueError, ZeroDivisionError):
                pass

    if species_l == "citrus" and any(below(n) for n in ("Ca", "K")):
        messages.append("Adjust fertilizer ratios for higher Ca/K supply for Citrus.")

    if species_l == "begonia" and below("Mg"):
        messages.append("Increase Mg supplementation for Begonia.")

    return messages
