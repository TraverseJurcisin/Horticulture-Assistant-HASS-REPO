from typing import List, Dict, Optional
from decimal import Decimal


class CostAnalysis:
    def __init__(self):
        self.inventory: Dict[str, Dict] = {}

    def update_inventory(self, inventory_data: Dict[str, Dict]):
        """
        Update the product inventory with pricing and packaging information.
        """
        self.inventory = inventory_data

    def calculate_product_cost(self, product_id: str, amount_used: float, unit: str) -> Optional[float]:
        """
        Calculate the cost of the amount of product used, based on matching the best unit price.
        """
        if product_id not in self.inventory:
            return None

        entries = self.inventory[product_id].get("instances", [])
        if not entries:
            return None

        # Sort by best price per unit (smallest cost per unit mass or volume)
        sorted_entries = sorted(entries, key=lambda e: self._price_per_unit(e))
        for entry in sorted_entries:
            unit_type = entry.get("unit_type")
            price = entry.get("price")
            size = entry.get("size")

            if not all([price, size, unit_type]):
                continue

            if unit_type == unit:
                cost = (amount_used / size) * price
                return round(cost, 4)

        return None  # No match found

    def calculate_recipe_cost(self, recipe: List[Dict]) -> float:
        """
        recipe: list of dicts like:
        [
            {"product_id": "FoxFarm_GrowBig", "amount": 4.5, "unit": "g"},
            {"product_id": "Canna_CalMag", "amount": 2.0, "unit": "ml"},
        ]
        """
        total_cost = Decimal("0.00")

        for ingredient in recipe:
            cost = self.calculate_product_cost(
                ingredient["product_id"],
                ingredient["amount"],
                ingredient["unit"]
            )
            if cost:
                total_cost += Decimal(str(cost))

        return float(round(total_cost, 4))

    def _price_per_unit(self, entry: Dict) -> float:
        try:
            return entry["price"] / entry["size"]
        except (TypeError, ZeroDivisionError, KeyError):
            return float("inf")
