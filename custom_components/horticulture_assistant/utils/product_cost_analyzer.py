from typing import Literal, List, Dict, Optional


class ProductCostAnalyzer:
    @staticmethod
    def cost_per_unit(
        price: float,
        size: float,
        unit: Literal["L", "mL", "gal", "kg", "g", "oz"]
    ) -> float:
        """
        Calculates the cost per standard unit (1 L or 1 kg).
        :param price: Total price of the product package
        :param size: Size of the package in its specified unit
        :param unit: Unit of the package (volume or mass)
        :return: Cost per unit (USD)
        """
        conversions = {
            "L": 1,
            "mL": 1 / 1000,
            "gal": 3.78541,
            "kg": 1,
            "g": 1 / 1000,
            "oz": 0.0283495,
        }

        if unit not in conversions:
            raise ValueError(f"Unsupported unit: {unit}")

        size_in_standard = size * conversions[unit]
        if size_in_standard == 0:
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
                per_unit_prices.append(cost)
            except ValueError as e:
                continue

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
        """
        Estimates the cost of a single dose based on unit cost.
        """
        conversions = {
            "L": 1,
            "mL": 1 / 1000,
            "kg": 1,
            "g": 1 / 1000,
            "oz": 0.0283495,
        }

        if dose_unit not in conversions:
            raise ValueError(f"Unsupported dose unit: {dose_unit}")

        dose_in_standard = dose_amount * conversions[dose_unit]
        return round(cost_per_unit * dose_in_standard, 4)