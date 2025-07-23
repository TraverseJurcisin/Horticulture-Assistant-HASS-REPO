"""Helpers to compare fertilizer product pricing and ingredients.

The :func:`price_per_unit` function normalizes prices across units so
products can be compared easily. :func:`get_cheapest_option` returns the
least expensive product option given a sequence of :class:`ProductOption`.
:func:`compare_ingredient_costs` determines the minimum cost per mg of
active ingredient across options.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable


_UNIT_CONVERSIONS = {
    "kg": 1.0,
    "g": 0.001,
    "lb": 0.453592,
    "oz": 0.0283495,
    "L": 1.0,
    "mL": 0.001,
    "gal": 3.78541,
    "fl_oz": 0.0295735,
}


@dataclass
class ProductOption:
    """Fertilizer purchase option."""

    price: float
    quantity: float
    unit: str
    supplier: str
    ingredients: Dict[str, float] | None = None

    def price_per_unit(self) -> float:
        """Return price normalized to the base unit (kg or L)."""
        if self.unit not in _UNIT_CONVERSIONS:
            raise ValueError(f"Unsupported unit: {self.unit}")
        normalized = self.quantity * _UNIT_CONVERSIONS[self.unit]
        return self.price / normalized if normalized else 0.0


def price_per_unit(price: float, quantity: float, unit: str) -> float:
    """Return cost normalized to the base unit."""
    return ProductOption(price, quantity, unit, "").price_per_unit()


def get_cheapest_option(options: Iterable[ProductOption]) -> ProductOption | None:
    """Return the option with the lowest unit price."""
    best: ProductOption | None = None
    best_price = float("inf")
    for opt in options:
        unit_price = opt.price_per_unit()
        if unit_price < best_price:
            best_price = unit_price
            best = opt
    return best


def compare_ingredient_costs(options: Iterable[ProductOption]) -> Dict[str, float]:
    """Return lowest cost per mg for each ingredient across options."""
    costs: Dict[str, float] = {}
    for opt in options:
        if not opt.ingredients:
            continue
        for ing, mass_mg in opt.ingredients.items():
            if mass_mg <= 0:
                continue
            cost = opt.price / mass_mg
            if ing not in costs or cost < costs[ing]:
                costs[ing] = cost
    return costs
