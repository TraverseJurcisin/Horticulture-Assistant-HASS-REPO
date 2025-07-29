"""Dataset-backed catalog for fertilizer information."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict

from plant_engine.utils import lazy_dataset

DATA_FILE = "fertilizers/fertilizer_products.json"
PRICE_FILE = "fertilizers/fertilizer_prices.json"
SOLUBILITY_FILE = "fertilizer_solubility.json"
APPLICATION_FILE = "fertilizers/fertilizer_application_methods.json"
RATE_FILE = "fertilizers/fertilizer_application_rates.json"
COMPAT_FILE = "fertilizers/fertilizer_compatibility.json"
DILUTION_FILE = "fertilizers/fertilizer_dilution_limits.json"

_DATA = lazy_dataset(DATA_FILE)
_PRICES = lazy_dataset(PRICE_FILE)
_SOLUBILITY = lazy_dataset(SOLUBILITY_FILE)
_APPLICATION = lazy_dataset(APPLICATION_FILE)
_RATES = lazy_dataset(RATE_FILE)
_COMPAT = lazy_dataset(COMPAT_FILE)
_DILUTION = lazy_dataset(DILUTION_FILE)


@dataclass(frozen=True, slots=True)
class Fertilizer:
    """Fertilizer product information."""

    density_kg_per_l: float
    guaranteed_analysis: Dict[str, float]
    product_name: str | None = None
    wsda_product_number: str | None = None


class FertilizerCatalog:
    """Cached access to fertilizer datasets."""

    @staticmethod
    @lru_cache(maxsize=None)
    def inventory() -> Dict[str, Fertilizer]:
        data = _DATA()
        inv: Dict[str, Fertilizer] = {}
        for name, info in data.items():
            inv[name] = Fertilizer(
                density_kg_per_l=info.get("density_kg_per_l", 1.0),
                guaranteed_analysis=info.get("guaranteed_analysis", {}),
                product_name=info.get("product_name"),
                wsda_product_number=info.get("wsda_product_number"),
            )
        return inv

    @staticmethod
    @lru_cache(maxsize=None)
    def prices() -> Dict[str, float]:
        return _PRICES()

    @staticmethod
    @lru_cache(maxsize=None)
    def solubility() -> Dict[str, float]:
        return _SOLUBILITY()

    @staticmethod
    @lru_cache(maxsize=None)
    def application_methods() -> Dict[str, str]:
        return _APPLICATION()

    @staticmethod
    @lru_cache(maxsize=None)
    def application_rates() -> Dict[str, float]:
        return _RATES()

    @staticmethod
    @lru_cache(maxsize=None)
    def compatibility() -> Dict[str, Dict[str, str]]:
        raw = _COMPAT()
        mapping: Dict[str, Dict[str, str]] = {}
        for fert, info in raw.items():
            if not isinstance(info, dict):
                continue
            inner: Dict[str, str] = {}
            for other, reason in info.items():
                inner[str(other)] = str(reason)
            if inner:
                mapping[fert] = inner
        return mapping

    @staticmethod
    @lru_cache(maxsize=None)
    def dilution_limits() -> Dict[str, float]:
        return _DILUTION()

    def list_products(self) -> list[str]:
        inv = self.inventory()
        return sorted(inv.keys(), key=lambda pid: inv[pid].product_name or pid)

    def get_product_info(self, fertilizer_id: str) -> Fertilizer:
        inv = self.inventory()
        if fertilizer_id not in inv:
            raise KeyError(f"Unknown fertilizer '{fertilizer_id}'")
        return inv[fertilizer_id]


CATALOG = FertilizerCatalog()

__all__ = ["Fertilizer", "FertilizerCatalog", "CATALOG"]
