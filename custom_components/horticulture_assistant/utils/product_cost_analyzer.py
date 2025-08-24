"""Utility helpers for comparing product prices across units."""

from typing import Literal

try:
    from .unit_utils import UNIT_CONVERSIONS, to_base
except ImportError:  # pragma: no cover - fallback for direct execution
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "unit_utils",
        Path(__file__).resolve().parent / "unit_utils.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    UNIT_CONVERSIONS = mod.UNIT_CONVERSIONS  # type: ignore
    to_base = mod.to_base  # type: ignore

__all__ = [
    "ProductCostAnalyzer",
]


class ProductCostAnalyzer:
    """Convenience methods for normalizing product pricing."""

    @staticmethod
    def cost_per_unit(
        price: float, size: float, unit: Literal["L", "mL", "gal", "kg", "g", "oz"]
    ) -> float:
        """Return cost per liter or kilogram for a packaged product."""

        if unit not in UNIT_CONVERSIONS:
            raise ValueError(f"Unsupported unit: {unit}")

        size_in_standard = to_base(size, unit)
        if size_in_standard <= 0:
            raise ValueError("Size must be greater than zero")

        return round(price / size_in_standard, 4)

    @staticmethod
    def compare_sources(price_data: list[dict[str, float]]) -> dict[str, float]:
        """
        Compares multiple listings of the same product to find best value.
        Each dict in the list should contain: price, size, and unit.
        """
        per_unit_prices = []
        for entry in price_data:
            try:
                cost = ProductCostAnalyzer.cost_per_unit(
                    entry["price"], entry["size"], entry["unit"]
                )
            except (KeyError, ValueError):
                continue
            per_unit_prices.append(cost)

        if not per_unit_prices:
            raise ValueError("No valid pricing data")

        return {
            "min_cost_per_unit": min(per_unit_prices),
            "max_cost_per_unit": max(per_unit_prices),
            "avg_cost_per_unit": round(sum(per_unit_prices) / len(per_unit_prices), 4),
        }

    @staticmethod
    def cost_of_dose(
        cost_per_unit: float, dose_amount: float, dose_unit: Literal["L", "kg", "mL", "g", "oz"]
    ) -> float:
        """Return cost for a single application amount."""

        if dose_unit not in UNIT_CONVERSIONS:
            raise ValueError(f"Unsupported dose unit: {dose_unit}")

        dose_in_standard = to_base(dose_amount, dose_unit)
        return round(cost_per_unit * dose_in_standard, 4)
