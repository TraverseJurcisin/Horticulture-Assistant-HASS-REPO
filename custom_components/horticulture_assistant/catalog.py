"""Dataset-backed catalog for fertilizer information."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

from .engine.plant_engine.utils import lazy_dataset

DATA_FILE = "fertilizers/fertilizer_products.json"
PRICE_FILE = "fertilizers/fertilizer_prices.json"
SOLUBILITY_FILE = "fertilizers/fertilizer_solubility.json"
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
    guaranteed_analysis: dict[str, float]
    product_name: str | None = None
    wsda_product_number: str | None = None


class FertilizerCatalog:
    """Cached access to fertilizer datasets."""

    @staticmethod
    @cache
    def inventory() -> dict[str, Fertilizer]:
        data = _DATA()
        inv: dict[str, Fertilizer] = {}
        for name, info in data.items():
            inv[name] = Fertilizer(
                density_kg_per_l=info.get("density_kg_per_l", 1.0),
                guaranteed_analysis=info.get("guaranteed_analysis", {}),
                product_name=info.get("product_name"),
                wsda_product_number=info.get("wsda_product_number"),
            )
        return inv

    @staticmethod
    @cache
    def prices() -> dict[str, float]:
        return _PRICES()

    @staticmethod
    @cache
    def solubility() -> dict[str, float]:
        return _SOLUBILITY()

    @staticmethod
    @cache
    def application_methods() -> dict[str, str]:
        return _APPLICATION()

    @staticmethod
    @cache
    def application_rates() -> dict[str, float]:
        return _RATES()

    @staticmethod
    @cache
    def compatibility() -> dict[str, dict[str, str]]:
        raw = _COMPAT()
        mapping: dict[str, dict[str, str]] = {}
        for fert, info in raw.items():
            if not isinstance(info, dict):
                continue
            inner: dict[str, str] = {}
            for other, reason in info.items():
                inner[str(other)] = str(reason)
            if inner:
                mapping[fert] = inner
        return mapping

    @staticmethod
    @cache
    def dilution_limits() -> dict[str, float]:
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
