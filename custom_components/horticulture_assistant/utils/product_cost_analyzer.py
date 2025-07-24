"""Utility helpers for comparing product prices across units."""

from typing import Dict, List, Literal

__all__ = [
    "ProductCostAnalyzer",
]


# Conversion factors to liters or kilograms
UNIT_CONVERSIONS = {
    "L": 1.0,
    "mL": 1.0 / 1000,
    "gal": 3.78541,
    "kg": 1.0,
    "g": 1.0 / 1000,
    "oz": 0.0283495,
}


class ProductCostAnalyzer:
    """Convenience methods for normalizing product pricing."""

    @staticmethod
    def cost_per_unit(
        price: float,
        size: float,
        unit: Literal["L", "mL", "gal", "kg", "g", "oz"]
    ) -> float:
        """Return cost per liter or kilogram for a packaged product."""

        if unit not in UNIT_CONVERSIONS:
            raise ValueError(f"Unsupported unit: {unit}")

        size_in_standard = size * UNIT_CONVERSIONS[unit]
        if size_in_standard <= 0:
            raise ValueError("Size must be greater than zero")

        return round(price / size_in_standard, 4)

    @staticmethod
    def compare_sources(
        price_data: List[Dict[str, float]]
    ) -> Dict[str, float]:
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
        cost_per_unit: float,
        dose_amount: float,
        dose_unit: Literal["L", "kg", "mL", "g", "oz"]
    ) -> float:
        """Return cost for a single application amount."""

        if dose_unit not in UNIT_CONVERSIONS:
            raise ValueError(f"Unsupported dose unit: {dose_unit}")

        dose_in_standard = dose_amount * UNIT_CONVERSIONS[dose_unit]
        return round(cost_per_unit * dose_in_standard, 4)
