"""Simple utilities for logging nutrient applications."""

from dataclasses import dataclass, field
from typing import Dict, Optional, List, Iterable
from datetime import datetime, timedelta
from collections import defaultdict

@dataclass
class NutrientEntry:
    """Mapping of an element to its concentration in a product."""

    element: str
    value_mg_per_kg: float
    source_compound: Optional[str] = None

@dataclass
class ProductNutrientProfile:
    """Profile describing nutrient concentrations for a product."""

    product_id: str
    nutrient_map: Dict[str, NutrientEntry] = field(default_factory=dict)

    def add_element(self, element: str, value: float, source: Optional[str] = None) -> None:
        """Register a nutrient value in ``mg/kg`` for the product."""

        self.nutrient_map[element] = NutrientEntry(element, value, source)

    def get_ppm_from_dose(self, dose_g: float, solution_kg: float = 1.0) -> Dict[str, float]:
        """Return delivered ppm for ``dose_g`` grams in ``solution_kg`` kilograms."""

        ppm_map: Dict[str, float] = {}
        for nutrient in self.nutrient_map.values():
            total_mg = dose_g * (nutrient.value_mg_per_kg / 1000)
            ppm = total_mg / solution_kg
            ppm_map[nutrient.element] = round(ppm, 4)
        return ppm_map

@dataclass
class NutrientDeliveryRecord:
    """Record describing a single nutrient application."""

    plant_id: str
    batch_id: str
    timestamp: datetime
    ppm_delivered: Dict[str, float]
    volume_l: float

@dataclass
class NutrientTracker:
    """Track nutrient deliveries and summarize totals."""

    product_profiles: Dict[str, ProductNutrientProfile] = field(default_factory=dict)
    delivery_log: List[NutrientDeliveryRecord] = field(default_factory=list)

    def register_product(self, profile: ProductNutrientProfile) -> None:
        """Register a nutrient profile so it can be referenced by ``log_delivery``."""

        self.product_profiles[profile.product_id] = profile

    def log_delivery(self, plant_id: str, batch_id: str, product_id: str, dose_g: float, volume_l: float) -> None:
        """Log a nutrient application for ``plant_id``."""

        if product_id not in self.product_profiles:
            raise ValueError(f"Unknown product_id {product_id}")

        profile = self.product_profiles[product_id]
        ppm_map = profile.get_ppm_from_dose(dose_g, volume_l)

        record = NutrientDeliveryRecord(
            plant_id=plant_id,
            batch_id=batch_id,
            timestamp=datetime.now(),
            ppm_delivered=ppm_map,
            volume_l=volume_l,
        )
        self.delivery_log.append(record)

    def summarize_nutrients(self, plant_id: Optional[str] = None) -> Dict[str, float]:
        """Return total ppm delivered across all logged applications."""

        summary: Dict[str, float] = defaultdict(float)
        for record in self.delivery_log:
            if plant_id and record.plant_id != plant_id:
                continue
            for element, ppm in record.ppm_delivered.items():
                summary[element] += ppm
        return dict(summary)

    def summarize_mg_for_day(self, date: datetime, plant_id: Optional[str] = None) -> Dict[str, float]:
        """Return total milligrams delivered on ``date``."""

        summary: Dict[str, float] = defaultdict(float)
        for record in self.delivery_log:
            if plant_id and record.plant_id != plant_id:
                continue
            if record.timestamp.date() != date.date():
                continue
            for element, ppm in record.ppm_delivered.items():
                summary[element] += ppm * record.volume_l
        return dict(summary)

    def summarize_mg_for_period(
        self, start: datetime, end: datetime, plant_id: Optional[str] = None
    ) -> Dict[str, float]:
        """Return milligrams delivered between ``start`` and ``end`` (inclusive)."""

        if start > end:
            raise ValueError("start must not be after end")

        summary: Dict[str, float] = defaultdict(float)
        for record in self.delivery_log:
            if plant_id and record.plant_id != plant_id:
                continue
            if not (start <= record.timestamp <= end):
                continue
            for element, ppm in record.ppm_delivered.items():
                summary[element] += ppm * record.volume_l
        return dict(summary)

    def summarize_mg_since(
        self, days: int, plant_id: Optional[str] = None, *, now: Optional[datetime] = None
    ) -> Dict[str, float]:
        """Return milligrams delivered in the last ``days`` days."""

        if days < 0:
            raise ValueError("days must be non-negative")

        ref = now or datetime.now()
        start = ref - timedelta(days=days)
        return self.summarize_mg_for_period(start, ref, plant_id)
