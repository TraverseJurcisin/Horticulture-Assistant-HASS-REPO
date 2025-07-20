from dataclasses import dataclass, field
from typing import Optional, List
import datetime
import json

@dataclass
class ProductInstance:
    product_name: str
    vendor: str
    size: float
    size_unit: str
    cost: float
    purchase_date: str
    manufacture_date: Optional[str] = None
    expiration_date: Optional[str] = None
    temperature_sensitive: bool = False
    mineral_based: bool = True
    ec: Optional[float] = None
    ph: Optional[float] = None
    concentration_note: Optional[str] = None
    derived_from: List[str] = field(default_factory=list)

class ProductTracker:
    def __init__(self):
        self.inventory: List[ProductInstance] = []

    def add_product(self, instance: ProductInstance):
        self.inventory.append(instance)

    def get_valid_products(self, product_name: str, as_of_date: Optional[str] = None) -> List[ProductInstance]:
        if as_of_date is None:
            as_of_date = datetime.date.today().isoformat()

        def is_valid(prod: ProductInstance) -> bool:
            if not prod.expiration_date or prod.mineral_based:
                return True
            return prod.expiration_date > as_of_date

        return [p for p in self.inventory if p.product_name == product_name and is_valid(p)]

    def total_available(self, product_name: str, unit: str) -> float:
        valid = self.get_valid_products(product_name)
        return sum(p.size for p in valid if p.size_unit == unit)

    def get_product_by_vendor(self, product_name: str, vendor: str) -> List[ProductInstance]:
        return [p for p in self.inventory if p.product_name == product_name and p.vendor == vendor]

    def export_json(self) -> str:
        return json.dumps([p.__dict__ for p in self.inventory], indent=2)