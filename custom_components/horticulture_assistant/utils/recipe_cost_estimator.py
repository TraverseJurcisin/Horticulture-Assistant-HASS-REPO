"""Helpers for estimating fertigation recipe costs."""



def estimate_recipe_cost(
    product_dose_rates: dict[str, float],
    product_costs_per_unit: dict[str, float],
    total_volume_liters: float,
    unit_type: str = "L",
) -> dict[str, float]:
    """Return cost estimate for a nutrient recipe.

    Parameters
    ----------
    product_dose_rates : Dict[str, float]
        Mapping of product ID to application rate per liter.
    product_costs_per_unit : Dict[str, float]
        Mapping of product ID to cost per unit (e.g. dollars per liter or kg).
    total_volume_liters : float
        Volume of solution to prepare in liters. Must be positive.
    unit_type : str, optional
        Unit type for ``product_costs_per_unit`` (``"L"`` or ``"kg"``).

    Returns
    -------
    Dict[str, float]
        Dictionary with ``"total_cost"`` and per-product costs.
    """
    if total_volume_liters <= 0:
        raise ValueError("total_volume_liters must be positive")

    product_cost_breakdown: dict[str, float] = {}
    total_cost = 0.0

    for product_id, dose_per_liter in product_dose_rates.items():
        unit_cost = product_costs_per_unit.get(product_id, 0.0)
        total_dose = dose_per_liter * total_volume_liters
        cost = total_dose * unit_cost
        product_cost_breakdown[product_id] = round(cost, 4)
        total_cost += cost

    return {
        "total_cost": round(total_cost, 4),
        "product_costs": product_cost_breakdown,
        "unit_type": unit_type,
    }
