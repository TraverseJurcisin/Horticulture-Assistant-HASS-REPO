from typing import Dict, Optional
from datetime import datetime

class FertilizerProduct:
    def __init__(
        self,
        product_id: str,
        name: str,
        is_liquid: bool,
        density_kg_per_l: Optional[float],
        analysis: Dict[str, float],  # element_name -> % concentration
        ingredients: Dict[str, Dict[str, str]],  # ingredient -> {"amount": float, "unit": str}
        derived_type: str,  # "mineral", "organic", "hybrid"
        typical_pH: Optional[float] = None,
        typical_EC: Optional[float] = None,
        precipitation_risk: Optional[str] = "low",
    ):
        self.product_id = product_id
        self.name = name
        self.is_liquid = is_liquid
        self.density_kg_per_l = density_kg_per_l
        self.analysis = analysis
        self.ingredients = ingredients
        self.derived_type = derived_type
        self.typical_pH = typical_pH
        self.typical_EC = typical_EC
        self.precipitation_risk = precipitation_risk


class FertilizerListing:
    def __init__(
        self,
        listing_id: str,
        product_id: str,
        distributor: str,
        form: str,  # "liquid" or "solid"
        package_size: float,  # in L or kg
        price_usd: float,
        purchase_date: Optional[str] = None,
        expiration_date: Optional[str] = None,
        date_of_manufacture: Optional[str] = None,
        storage_location: Optional[str] = None,
        available: bool = True,
        source_ingredients: Optional[Dict[str, str]] = None,
    ):
        self.listing_id = listing_id
        self.product_id = product_id
        self.distributor = distributor
        self.form = form
        self.package_size = package_size
        self.price_usd = price_usd
        self.purchase_date = purchase_date
        self.expiration_date = expiration_date
        self.date_of_manufacture = date_of_manufacture
        self.storage_location = storage_location
        self.available = available
        self.source_ingredients = source_ingredients or {}

        self.cost_per_unit = self.calculate_cost_per_unit()
        self.expired = self.check_if_expired()

    def calculate_cost_per_unit(self) -> float:
        if self.package_size > 0:
            return self.price_usd / self.package_size
        return 0.0

    def check_if_expired(self) -> bool:
        if not self.expiration_date:
            return False
        try:
            exp_date = datetime.strptime(self.expiration_date, "%Y-%m-%d")
            return exp_date < datetime.today()
        except ValueError:
            return False


# Example instantiation
magriculture = FertilizerProduct(
    product_id="magriculture",
    name="Magriculture",
    is_liquid=False,
    density_kg_per_l=None,
    analysis={"Mg": 9.8, "S": 12.9},
    ingredients={
        "Magnesium Sulfate Heptahydrate": {
            "amount": 100.0,
            "unit": "percent_wt"
        }
    },
    derived_type="mineral",
    typical_pH=6.5,
    typical_EC=2.3,
    precipitation_risk="low"
)

magriculture_listing = FertilizerListing(
    listing_id="magriculture_htg_5kg",
    product_id="magriculture",
    distributor="HTG Supply",
    form="solid",
    package_size=5.0,
    price_usd=23.99,
    purchase_date="2024-06-15",
    expiration_date="2027-06-01",
    date_of_manufacture="2024-04-01",
    storage_location="garage_rack_2",
    source_ingredients={"Magnesium Sulfate Heptahydrate": "K+S Germany"}
)