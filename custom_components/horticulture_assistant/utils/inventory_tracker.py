from datetime import date
from typing import List, Dict, Optional


class FertilizerLot:
    def __init__(
        self,
        lot_id: str,
        product_name: str,
        manufacturer: str,
        supplier: str,
        date_of_manufacture: date,
        date_of_purchase: date,
        expiration_date: Optional[date],
        batch_weight_kg: float,
        unit_type: str,
        base_cost: float,
        derived_from: List[str],
        is_biological: bool = False,
    ):
        self.lot_id = lot_id
        self.product_name = product_name
        self.manufacturer = manufacturer
        self.supplier = supplier
        self.date_of_manufacture = date_of_manufacture
        self.date_of_purchase = date_of_purchase
        self.expiration_date = expiration_date
        self.batch_weight_kg = batch_weight_kg
        self.unit_type = unit_type  # kg, L, etc.
        self.base_cost = base_cost  # cost for entire lot
        self.derived_from = derived_from
        self.is_biological = is_biological

        self.usage_history: List[Dict] = []  # stores when/where/how_much used

    def log_use(
        self,
        date_applied: date,
        amount_kg: float,
        used_in_recipe: str,
        zone_id: str,
    ):
        self.usage_history.append(
            {
                "date": date_applied,
                "amount_used_kg": amount_kg,
                "recipe": used_in_recipe,
                "zone": zone_id,
            }
        )

    def remaining_kg(self) -> float:
        used = sum(entry["amount_used_kg"] for entry in self.usage_history)
        return self.batch_weight_kg - used

    def is_expired(self, today: Optional[date] = None) -> bool:
        if not self.expiration_date:
            return False
        return (today or date.today()) > self.expiration_date

    def is_precipitation_sensitive(self) -> bool:
        sensitive_ingredients = [
            "calcium nitrate",
            "iron sulfate",
            "magnesium sulfate",
            "ammonium phosphate",
            "potassium phosphate",
        ]
        return any(
            ingr.lower() in str(self.derived_from).lower()
            for ingr in sensitive_ingredients
        )

    def estimated_cost_per_kg(self) -> float:
        return self.base_cost / self.batch_weight_kg if self.batch_weight_kg else 0.0

    def summary(self) -> Dict:
        return {
            "lot_id": self.lot_id,
            "product": self.product_name,
            "manufacturer": self.manufacturer,
            "supplier": self.supplier,
            "mfg_date": self.date_of_manufacture.isoformat(),
            "purchase_date": self.date_of_purchase.isoformat(),
            "expiration": self.expiration_date.isoformat()
            if self.expiration_date
            else None,
            "remaining_kg": self.remaining_kg(),
            "sensitive": self.is_precipitation_sensitive(),
            "cost_per_kg": self.estimated_cost_per_kg(),
            "biological": self.is_biological,
            "uses": self.usage_history,
        }