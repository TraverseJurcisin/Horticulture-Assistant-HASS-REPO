from typing import Dict


def estimate_recipe_cost(
    product_dose_rates: Dict[str, float],
    product_costs_per_unit: Dict[str, float],
    total_volume_liters: float,
    unit_type: str = "L"
) -> Dict[str, float]:
    """
    Estimate the cost of a recipe based on product dose rates and unit costs.

    Args:
        product_dose_rates: {product_id: rate per liter}
        product_costs_per_unit: {product_id: cost per unit (e.g., $/L, $/kg)}
        total_volume_liters: total batch size in liters
        unit_type: "L" for liquid or "kg" for solid (controls unit interpretation)

    Returns:
        Dict with cost breakdown per product and total cost.
    """
    product_cost_breakdown = {}
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
        "unit_type": unit_type
    }
