from dataclasses import asdict, dataclass, field


@dataclass
class ProductPackaging:
    """Packaging information for a fertilizer product."""

    volume: float
    unit: str
    distributor: str
    price: float
    sku: str
    msrp: float | None = None
    link: str | None = None

    def cost_per_unit(self) -> float:
        """Return price normalized to a single unit."""
        return self.price / self.volume if self.volume else 0.0

    def describe(self) -> dict:
        """Return a serialisable representation including unit cost."""
        data = asdict(self)
        data["cost_per_unit"] = self.cost_per_unit()
        return data


@dataclass
class FertilizerProduct:
    """Representation of a fertilizer product and pricing options."""

    name: str
    manufacturer: str
    form: str
    derived_from: list[str]
    base_composition: dict[str, float]
    density_kg_per_L: float | None = None
    bio_based: bool = False
    packaging_options: list[ProductPackaging] = field(default_factory=list)

    def add_packaging(self, packaging: ProductPackaging) -> None:
        """Register an available package size."""
        self.packaging_options.append(packaging)

    def get_best_price_per_unit(self, unit_preference: str = "kg") -> float | None:
        """Return the lowest unit price for the preferred unit if available."""
        prices = [pkg.cost_per_unit() for pkg in self.packaging_options if pkg.unit.lower() == unit_preference.lower()]
        return min(prices) if prices else None

    def describe(self) -> dict:
        """Return a serialisable summary including best unit price."""
        data = asdict(self)
        data["best_price_per_unit"] = self.get_best_price_per_unit()
        data["packaging_options"] = [pkg.describe() for pkg in self.packaging_options]
        return data


__all__ = ["ProductPackaging", "FertilizerProduct"]
