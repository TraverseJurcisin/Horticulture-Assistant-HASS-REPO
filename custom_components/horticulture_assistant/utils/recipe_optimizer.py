"""
Core module for optimizing fertilizer recipes to meet plant nutrient targets.
"""


def optimize_recipe(plant_profile: dict[str, float], products: list[dict]) -> dict:
    """
    Generate a fertilizer recipe to meet nutrient targets specified in a plant profile.

    Parameters:
    - plant_profile: dict with nutrient targets for the current growth stage, e.g.
        {"nutrient_targets": {"N": 100.0, "P": 50.0, "K": 150.0, "Fe": 2.0}}
        Targets are in mg of nutrient per liter of solution.
    - products: list of fertilizer products available. Each product is a dict with keys:
        - "name": product name
        - "form": "solid" or "liquid"
        - "analysis": dict of nutrient percentages by weight (e.g. {"N": 15.5, "P": 20.0})
        - "price_per_unit": cost per gram for solids or per mL for liquids.

    Returns:
    A dict with the proposed recipe:
        {
            "ingredients": [
                {"product": name, "dose": amount, "unit": unit, "cost": cost},
                ...
            ],
            "total_cost": total_cost,
            "total_volume": total_volume_liters
        }

    Raises:
        ValueError: if the targets cannot be met with the available products.
    """
    # Extract nutrient targets (mg per liter)
    targets = plant_profile.get("nutrient_targets", {})
    if not targets:
        raise ValueError("Plant profile must include 'nutrient_targets' for current stage")

    # Check that each required nutrient is present in at least one product
    for nutrient, target in targets.items():
        if target is None or target <= 0:
            continue
        found = any((nutrient in prod.get("analysis", {}) and prod["analysis"][nutrient] > 0) for prod in products)
        if not found:
            raise ValueError(f"No available product contains nutrient '{nutrient}' to meet target {target} mg/L")

    # Initialize remaining targets (mg)
    remaining = {nut: val for nut, val in targets.items() if val > 0}
    # Track doses (grams for solids, mL for liquids) for each product by name
    doses: dict[str, float] = {}
    # Total additional volume (mL) from liquid products
    liquid_volume_ml = 0.0

    # Sort nutrients by descending target to prioritize largest needs
    nutrients_sorted = sorted(remaining.keys(), key=lambda x: remaining[x], reverse=True)
    for nutrient in nutrients_sorted:
        needed = remaining.get(nutrient, 0.0)
        if needed <= 0:
            continue

        # Select best product: lowest cost per mg of this nutrient
        best_prod = None
        best_cost_per_mg = float("inf")
        for prod in products:
            analysis = prod.get("analysis", {})
            if nutrient not in analysis or analysis[nutrient] <= 0:
                continue
            # mg of nutrient per gram of product
            mg_per_g = analysis[nutrient] * 10.0  # 1g yields (percent/100)*1000 mg
            if mg_per_g <= 0:
                continue
            cost = prod.get("price_per_unit", 0.0)
            if cost <= 0:
                continue
            cost_per_mg = cost / mg_per_g
            if cost_per_mg < best_cost_per_mg:
                best_cost_per_mg = cost_per_mg
                best_prod = prod

        if not best_prod:
            raise ValueError(f"No suitable product found to meet nutrient '{nutrient}'")

        # Calculate required dose of the chosen product (in its unit) to meet the nutrient need
        analysis_val = best_prod["analysis"][nutrient]
        mg_per_g = analysis_val * 10.0
        dose_g = needed / mg_per_g
        dose_g = round(dose_g, 4)

        prod_name = best_prod["name"]
        doses[prod_name] = doses.get(prod_name, 0.0) + dose_g

        # Subtract provided nutrients from remaining targets
        for nut, pct in best_prod.get("analysis", {}).items():
            if nut in remaining and remaining[nut] > 0:
                mg_provided = dose_g * (pct * 10.0)
                remaining[nut] = max(remaining[nut] - mg_provided, 0.0)

        # If the product is liquid, convert its dose to volume and add to total volume
        if best_prod.get("form") == "liquid":
            density = best_prod.get("density_g_per_ml", 1.0)  # default assume 1 g/mL
            volume_ml = dose_g / density
            liquid_volume_ml += volume_ml

    # Check if any nutrient targets remain unmet
    unmet = {nut: amt for nut, amt in remaining.items() if amt > 1e-3}
    if unmet:
        raise ValueError(f"Could not meet all targets, remaining: {unmet}")

    # Build the recipe output
    recipe_ingredients = []
    total_cost = 0.0
    for prod_name, dose in doses.items():
        prod = next((p for p in products if p["name"] == prod_name), None)
        if not prod:
            continue
        unit = "g" if prod.get("form") == "solid" else "mL"
        price = prod.get("price_per_unit", 0.0)
        cost = dose * price
        recipe_ingredients.append({"product": prod_name, "dose": dose, "unit": unit, "cost": round(cost, 2)})
        total_cost += cost

    total_volume_liters = (1000.0 + liquid_volume_ml) / 1000.0  # base 1L plus liquids

    return {
        "ingredients": recipe_ingredients,
        "total_cost": round(total_cost, 2),
        "total_volume": round(total_volume_liters, 3),
    }


# Example usage (mock data for demonstration)
if __name__ == "__main__":
    example_profile = {"nutrient_targets": {"N": 150.0, "P": 50.0, "K": 150.0, "Fe": 2.0, "Mg": 20.0}}
    example_products = [
        {
            "name": "CalNitrate",
            "form": "solid",
            "analysis": {"N": 15.5, "Ca": 19.0},
            "price_per_unit": 0.01,
        },
        {
            "name": "SuperPhosphate",
            "form": "solid",
            "analysis": {"P": 20.0, "Ca": 15.0},
            "price_per_unit": 0.015,
        },
        {
            "name": "PotassiumNitrate",
            "form": "solid",
            "analysis": {"K": 13.0, "N": 13.0},
            "price_per_unit": 0.012,
        },
        {
            "name": "MagnesiumSulfate",
            "form": "solid",
            "analysis": {"Mg": 9.6, "S": 13.0},
            "price_per_unit": 0.008,
        },
        {"name": "IronChelate", "form": "solid", "analysis": {"Fe": 6.0}, "price_per_unit": 0.05},
    ]
    try:
        recipe = optimize_recipe(example_profile, example_products)
        print("Proposed recipe:", recipe)
    except ValueError as e:
        print("Error:", e)
