from typing import Dict, List


class ProductPackaging:
    def __init__(
        self,
        volume: float,
        unit: str,
        distributor: str,
        price: float,
        sku: str,
        msrp: float = None,
        link: str = None,
    ):
        self.volume = volume  # e.g., 1.0
        self.unit = unit  # e.g., 'L', 'kg'
        self.distributor = distributor
        self.price = price  # price paid or listed price
        self.sku = sku
        self.msrp = msrp
        self.link = link

    def cost_per_unit(self) -> float:
        return self.price / self.volume if self.volume else 0.0

    def describe(self) -> Dict:
        return {
            "sku": self.sku,
            "volume": self.volume,
            "unit": self.unit,
            "distributor": self.distributor,
            "price": self.price,
            "msrp": self.msrp,
            "link": self.link,
            "cost_per_unit": self.cost_per_unit(),
        }


class FertilizerProduct:
    def __init__(
        self,
        name: str,
        manufacturer: str,
        form: str,  # e.g., 'liquid', 'granular'
        derived_from: List[str],
        base_composition: Dict[str, float],  # e.g., {'N': 5.0, 'Ca': 3.0}
        density_kg_per_L: float = None,
        bio_based: bool = False,
    ):
        self.name = name
        self.manufacturer = manufacturer
        self.form = form
        self.derived_from = derived_from
        self.base_composition = base_composition
        self.packaging_options: List[ProductPackaging] = []
        self.density_kg_per_L = density_kg_per_L
        self.bio_based = bio_based

    def add_packaging(self, packaging: ProductPackaging):
        self.packaging_options.append(packaging)

    def get_best_price_per_unit(self, unit_preference: str = "kg") -> float:
        best_price = float("inf")
        for pkg in self.packaging_options:
            if pkg.unit.lower() == unit_preference.lower():
                price = pkg.cost_per_unit()
                if price < best_price:
                    best_price = price
        return best_price if best_price != float("inf") else None

    def describe(self) -> Dict:
        return {
            "product_name": self.name,
            "manufacturer": self.manufacturer,
            "form": self.form,
            "bio_based": self.bio_based,
            "derived_from": self.derived_from,
            "base_composition": self.base_composition,
            "density_kg_per_L": self.density_kg_per_L,
            "best_price_per_unit": self.get_best_price_per_unit(),
            "packaging_options": [pkg.describe() for pkg in self.packaging_options],
        }