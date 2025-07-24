from typing import Dict, List


def calculate_cost_per_element_ppm(
    price_usd: float,
    weight_kg: float,
    composition: Dict[str, float],
) -> Dict[str, float]:
    """
    Estimate the cost (in USD) per ppm of each element provided by a fertilizer product.

    Args:
        price_usd: total price paid for this package
        weight_kg: weight of the product in kilograms
        composition: dictionary of element -> % by weight (guaranteed analysis)

    Returns:
        Dictionary of element -> cost per ppm (mg/kg)
    """

    element_costs = {}
    for element, percent in composition.items():
        mg_element = percent * 10_000  # % by weight to mg/kg
        if mg_element > 0:
            cost_per_mg = price_usd / (weight_kg * mg_element)
            element_costs[element] = cost_per_mg * 1_000  # convert to ppm

    return element_costs


def compare_product_prices(
    products: List[Dict],
    element: str,
) -> List[Dict]:
    """
    Given a list of fertilizer products, compare them by cost per ppm for a specific element.

    Args:
        products: list of dicts with keys: 'name', 'price', 'weight_kg', 'composition'
        element: which element to evaluate (e.g., "N", "P", "K", etc.)

    Returns:
        Sorted list of dicts, cheapest first
    """

    estimates = []
    for product in products:
        name = product["name"]
        cost = calculate_cost_per_element_ppm(
            product["price"],
            product["weight_kg"],
            product["composition"],
        )

        ppm_cost = cost.get(element)
        if ppm_cost is not None:
            estimates.append({
                "name": name,
                "cost_per_ppm": round(ppm_cost, 5),
                "price": product["price"],
                "weight_kg": product["weight_kg"],
            })

    return sorted(estimates, key=lambda x: x["cost_per_ppm"])
