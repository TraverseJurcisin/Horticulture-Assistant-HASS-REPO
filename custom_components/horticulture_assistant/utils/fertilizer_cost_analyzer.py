from typing import List, Dict


class FertilizerCostAnalyzer:
    @staticmethod
    def calculate_price_per_unit(price: float, quantity: float, unit: str) -> float:
        """
        Converts a price and quantity into price per standardized unit.
        Supports 'kg', 'g', 'lb', 'oz', 'L', 'mL', 'gal', 'fl_oz'
        """
        unit_conversions = {
            "kg": 1,
            "g": 0.001,
            "lb": 0.453592,
            "oz": 0.0283495,
            "L": 1,
            "mL": 0.001,
            "gal": 3.78541,
            "fl_oz": 0.0295735,
        }
        if unit not in unit_conversions:
            raise ValueError(f"Unsupported unit: {unit}")
        standardized_quantity = quantity * unit_conversions[unit]
        return price / standardized_quantity if standardized_quantity else 0.0

    @staticmethod
    def get_cheapest_supplier(options: List[Dict]) -> Dict:
        """
        Expects a list of product dictionaries with keys:
        - 'price'
        - 'quantity'
        - 'unit'
        - 'supplier'
        Returns the cheapest one by price per standardized unit.
        """
        best = None
        best_price = float("inf")

        for option in options:
            unit_price = FertilizerCostAnalyzer.calculate_price_per_unit(
                option["price"], option["quantity"], option["unit"]
            )
            if unit_price < best_price:
                best_price = unit_price
                best = option | {"price_per_unit": unit_price}

        return best or {}

    @staticmethod
    def compare_ingredient_costs(products: List[Dict]) -> Dict[str, float]:
        """
        Calculates cost per mg of each active ingredient across product options.
        Each product should have:
        - 'ingredients': {name: amount_in_mg}
        - 'price_per_unit': cost per kg or L
        - 'unit_weight': total weight or volume in kg or L
        """
        ingredient_costs = {}

        for product in products:
            for ingredient, mass_mg in product.get("ingredients", {}).items():
                if mass_mg > 0:
                    cost_per_mg = (
                        product["price_per_unit"] * product["unit_weight"] / mass_mg
                    )
                    if ingredient not in ingredient_costs:
                        ingredient_costs[ingredient] = cost_per_mg
                    else:
                        ingredient_costs[ingredient] = min(
                            ingredient_costs[ingredient], cost_per_mg
                        )

        return ingredient_costs