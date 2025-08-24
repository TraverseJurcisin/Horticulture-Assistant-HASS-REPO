"""Utilities for estimating crop revenue and profit."""

from __future__ import annotations

from collections.abc import Mapping

from . import yield_manager
from .utils import load_dataset, normalize_key

PRICE_FILE = "economics/crop_market_prices.json"
COST_FILE = "economics/crop_production_costs.json"

# Cached datasets at import time
_PRICES: dict[str, float] = load_dataset(PRICE_FILE)
_COSTS: dict[str, float] = load_dataset(COST_FILE)

__all__ = [
    "list_supported_crops",
    "get_crop_price",
    "estimate_revenue",
    "estimate_profit",
    "list_costed_crops",
    "get_crop_cost",
    "estimate_expected_revenue",
    "estimate_expected_profit",
]


def list_supported_crops() -> list[str]:
    """Return plant types with market price data."""
    return sorted(_PRICES.keys())


def get_crop_price(plant_type: str) -> float | None:
    """Return price per kilogram for ``plant_type`` if known."""
    key = normalize_key(plant_type)
    value = _PRICES.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def estimate_revenue(plant_id: str, plant_type: str) -> float:
    """Return revenue for harvested yield of ``plant_id``."""
    price = get_crop_price(plant_type)
    if price is None:
        return 0.0
    total_kg = yield_manager.get_total_yield(plant_id) / 1000.0
    return round(total_kg * price, 2)


def estimate_profit(
    plant_id: str,
    plant_type: str,
    costs: Mapping[str, float] | None = None,
) -> float:
    """Return estimated profit after subtracting ``costs`` from revenue."""
    revenue = estimate_revenue(plant_id, plant_type)
    total_cost = sum(float(v) for v in (costs or {}).values())
    return round(revenue - total_cost, 2)


def list_costed_crops() -> list[str]:
    """Return plant types with production cost data."""
    return sorted(_COSTS.keys())


def get_crop_cost(plant_type: str) -> float | None:
    """Return production cost per kilogram for ``plant_type`` if known."""
    key = normalize_key(plant_type)
    value = _COSTS.get(key)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def estimate_expected_revenue(plant_type: str) -> float | None:
    """Return expected revenue based on yield estimates."""
    yield_g = yield_manager.get_yield_estimate(plant_type)
    price = get_crop_price(plant_type)
    if yield_g is None or price is None:
        return None
    return round(yield_g / 1000.0 * price, 2)


def estimate_expected_profit(
    plant_type: str,
    extra_costs: Mapping[str, float] | None = None,
) -> float | None:
    """Return expected profit using yield and production cost estimates."""
    revenue = estimate_expected_revenue(plant_type)
    if revenue is None:
        return None
    cost_per_kg = get_crop_cost(plant_type) or 0.0
    yield_g = yield_manager.get_yield_estimate(plant_type) or 0.0
    base_cost = cost_per_kg * (yield_g / 1000.0)
    total_cost = base_cost + sum(float(v) for v in (extra_costs or {}).values())
    return round(revenue - total_cost, 2)
