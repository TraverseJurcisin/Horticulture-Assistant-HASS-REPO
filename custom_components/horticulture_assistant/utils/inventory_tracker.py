from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import uuid

@dataclass(slots=True)
class InventoryLot:
    """A single lot (batch) of a fertilizer or nutrient product."""
    product_name: str
    form: str           # "liquid" or "solid"
    vendor: str
    manufacture_date: datetime
    expiration_date: Optional[datetime]
    price: float        # price of this lot
    derived_ingredients: Dict[str, float]  # composition of the product (ingredient breakdown)
    storage_temp: Optional[float]  # recommended storage temperature (°C)
    is_biological: bool  # True if biological (organic/microbial), False if chemical/mineral
    initial_quantity: float        # initial quantity in this lot
    quantity_remaining: float      # current remaining quantity
    unit: str           # unit of measure for the quantity (e.g., "kg", "L")
    batch_id: str = field(default_factory=lambda: str(uuid.uuid4()))

class InventoryTracker:
    """Manage inventory of fertilizer/nutrient products (multiple lots, usage logging, expiration tracking)."""
    def __init__(self):
        self.inventory: Dict[str, List[InventoryLot]] = {}
        self.usage_log: List[Dict] = []

    def add_inventory(self, product_name: str, form: str, vendor: str,
                      manufacture_date: datetime, expiration_date: Optional[datetime],
                      price: float, derived_ingredients: Dict[str, float],
                      storage_temp: Optional[float], is_biological: bool,
                      quantity: float, unit: str):
        """Add a new inventory lot for a product."""
        lot = InventoryLot(
            product_name=product_name,
            form=form,
            vendor=vendor,
            manufacture_date=manufacture_date,
            expiration_date=expiration_date,
            price=price,
            derived_ingredients=derived_ingredients,
            storage_temp=storage_temp,
            is_biological=is_biological,
            initial_quantity=quantity,
            quantity_remaining=quantity,
            unit=unit
        )
        if product_name not in self.inventory:
            self.inventory[product_name] = []
        self.inventory[product_name].append(lot)

    def log_usage(self, product_name: str, amount: float, unit: str,
                  recipe: str, plant: str, date: Optional[datetime] = None) -> bool:
        """Deduct an amount of a product from inventory (using oldest lot(s) first) and log its usage.
        Logs the usage event with the recipe, plant, and date.
        Returns True if the inventory had enough product and the usage was logged, or False if insufficient quantity."""
        if product_name not in self.inventory:
            return False
        if date is None:
            date = datetime.now()
        lots = sorted(self.inventory[product_name], key=lambda x: (x.expiration_date or datetime.max, x.manufacture_date))
        amount_needed = amount
        for lot in lots:
            if lot.unit != unit:
                continue
            if lot.quantity_remaining <= 0:
                continue
            if lot.quantity_remaining >= amount_needed:
                lot.quantity_remaining -= amount_needed
                amount_needed = 0
                break
            else:
                amount_needed -= lot.quantity_remaining
                lot.quantity_remaining = 0.0
        # Remove depleted lots
        self.inventory[product_name] = [lot for lot in self.inventory[product_name] if lot.quantity_remaining > 0]
        if amount_needed > 1e-9:
            return False
        usage_event = {
            "date": date,
            "product": product_name,
            "recipe": recipe,
            "plant": plant,
            "amount": amount,
            "unit": unit
        }
        self.usage_log.append(usage_event)
        return True

    def get_total_quantity(self, product_name: str, unit: Optional[str] = None) -> float:
        """Get total remaining quantity of a product in inventory.
        If unit is specified, sums only that unit; otherwise, sums all remaining quantity (assuming uniform unit)."""
        if product_name not in self.inventory:
            return 0.0
        total = 0.0
        for lot in self.inventory[product_name]:
            if unit is None or lot.unit == unit:
                total += lot.quantity_remaining
        return total

    def get_expiring_lots(self, within_days: int = 30) -> List[InventoryLot]:
        """List all lots that will expire within the given number of days."""
        expiring = []
        now = datetime.now()
        threshold = now + timedelta(days=within_days)
        for product_lots in self.inventory.values():
            for lot in product_lots:
                if lot.expiration_date and lot.expiration_date <= threshold:
                    expiring.append(lot)
        return expiring

    def get_inventory_summary(self) -> List[Dict]:
        """Get a summary of the current inventory for each product.
        Returns a list of dicts containing product name, total remaining quantity, unit, number of lots, and nearest expiration date."""
        summary_list = []
        for product_name, lots in self.inventory.items():
            if not lots:
                continue
            # Assuming all lots of a product share the same unit
            unit = lots[0].unit
            total_quantity = sum(lot.quantity_remaining for lot in lots if lot.unit == unit)
            lot_count = len(lots)
            nearest_exp = None
            for lot in lots:
                if lot.expiration_date:
                    if nearest_exp is None or lot.expiration_date < nearest_exp:
                        nearest_exp = lot.expiration_date
            summary_list.append({
                "product": product_name,
                "total_quantity": total_quantity,
                "unit": unit,
                "lot_count": lot_count,
                "nearest_expiration": nearest_exp
            })
        return summary_list
