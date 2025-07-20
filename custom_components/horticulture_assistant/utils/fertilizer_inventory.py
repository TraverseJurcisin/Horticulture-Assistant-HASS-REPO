from typing import Dict, List, Optional
from datetime import datetime


class FertilizerProduct:
    def __init__(
        self,
        product_id: str,
        name: str,
        form: str,  # "liquid" or "solid"
        unit: str,  # e.g., "L", "mL", "kg", "g", "oz", "gal"
        derived_from: Dict[str, float],
        ph: Optional[float] = None,
        ec: Optional[float] = None,
        temp_sensitive_ingredients: Optional[List[str]] = None,
        expiration: Optional[datetime] = None,
        manufactured: Optional[datetime] = None,
    ):
        self.product_id = product_id
        self.name = name
        self.form = form
        self.unit = unit
        self.derived_from = derived_from  # {"Ammonium Nitrate": 120.0, "Magnesium Sulfate Heptahydrate": 1000.0}
        self.ph = ph
        self.ec = ec
        self.expiration = expiration
        self.manufactured = manufactured
        self.temp_sensitive_ingredients = temp_sensitive_ingredients or []

        self.price_history: List[Dict] = []  # [{"vendor": "HydroWorld", "unit_price": 18.99, "size": "1L", "date": datetime}]
        self.usage_log: List[Dict] = []  # [{"date": datetime, "amount_used": 200, "unit": "mL", "zone": "GH1"}]

    def add_price_entry(self, vendor: str, unit_price: float, size: str, date: Optional[datetime] = None):
        entry = {
            "vendor": vendor,
            "unit_price": round(unit_price, 2),
            "size": size,
            "date": date or datetime.now()
        }
        self.price_history.append(entry)

    def log_usage(self, amount_used: float, unit: str, zone: str):
        self.usage_log.append({
            "date": datetime.now(),
            "amount_used": amount_used,
            "unit": unit,
            "zone": zone
        })

    def get_latest_price(self) -> Optional[Dict]:
        if not self.price_history:
            return None
        return sorted(self.price_history, key=lambda x: x["date"], reverse=True)[0]

    def is_expired(self) -> bool:
        return self.expiration is not None and datetime.now() > self.expiration

    def needs_temp_protection(self, current_temp: float) -> bool:
        return any([
            ingr for ingr in self.temp_sensitive_ingredients
            if current_temp < 5 or current_temp > 30  # default temp sensitivity bounds
        ])


class FertilizerInventory:
    def __init__(self):
        self.products: Dict[str, FertilizerProduct] = {}

    def add_product(self, product: FertilizerProduct):
        self.products[product.product_id] = product

    def get_product(self, product_id: str) -> Optional[FertilizerProduct]:
        return self.products.get(product_id)

    def remove_product(self, product_id: str):
        if product_id in self.products:
            del self.products[product_id]

    def find_by_name(self, name: str) -> List[FertilizerProduct]:
        return [prod for prod in self.products.values() if name.lower() in prod.name.lower()]

    def find_expiring_products(self, days_before_expiry: int = 30) -> List[FertilizerProduct]:
        today = datetime.now()
        threshold = today.replace(hour=0, minute=0, second=0, microsecond=0)
        return [
            p for p in self.products.values()
            if p.expiration and (p.expiration - threshold).days <= days_before_expiry
        ]