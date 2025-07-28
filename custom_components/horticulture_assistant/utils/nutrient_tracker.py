"""Utilities for tracking nutrient applications and generating summaries."""

from dataclasses import dataclass, field, asdict
from typing import Dict, Optional, List, Iterable, Mapping, Any
from datetime import datetime, timedelta
from collections import defaultdict
import json
from pathlib import Path

from plant_engine.utils import load_dataset
from custom_components.horticulture_assistant.fertilizer_formulator import (
    convert_guaranteed_analysis,
)
from .nutrient_requirements import get_requirements

@dataclass(slots=True)
class NutrientEntry:
    """Mapping of an element to its concentration in a product."""

    element: str
    value_mg_per_kg: float
    source_compound: Optional[str] = None

@dataclass(slots=True)
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

@dataclass(slots=True)
class NutrientDeliveryRecord:
    """Record describing a single nutrient application."""

    plant_id: str
    batch_id: str
    timestamp: datetime
    ppm_delivered: Dict[str, float]
    volume_l: float

    def as_dict(self) -> Dict[str, Any]:
        """Return dictionary suitable for JSON serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["ppm_delivered"] = dict(self.ppm_delivered)
        return data

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "NutrientDeliveryRecord":
        """Create record from ``data`` loaded from JSON."""
        return NutrientDeliveryRecord(
            plant_id=str(data.get("plant_id", "")),
            batch_id=str(data.get("batch_id", "")),
            timestamp=datetime.fromisoformat(str(data["timestamp"])),
            ppm_delivered={k: float(v) for k, v in data.get("ppm_delivered", {}).items()},
            volume_l=float(data.get("volume_l", 0.0)),
        )

@dataclass(slots=True)
class NutrientTracker:
    """Track nutrient deliveries and summarize totals."""

    product_profiles: Dict[str, ProductNutrientProfile] = field(default_factory=dict)
    delivery_log: List[NutrientDeliveryRecord] = field(default_factory=list)
    _log_by_plant: Dict[str, List[NutrientDeliveryRecord]] = field(
        default_factory=lambda: defaultdict(list)
    )

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
        self._log_by_plant[plant_id].append(record)

    def save_log(self, path: str) -> None:
        """Save delivery log to ``path`` as JSON."""
        data = [rec.as_dict() for rec in self.delivery_log]
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_log(self, path: str) -> None:
        """Load delivery records from ``path`` if it exists."""
        p = Path(path)
        if not p.is_file():
            return
        records = json.loads(p.read_text(encoding="utf-8"))
        self.delivery_log.clear()
        self._log_by_plant.clear()
        for item in records:
            rec = NutrientDeliveryRecord.from_dict(item)
            self.delivery_log.append(rec)
            self._log_by_plant[rec.plant_id].append(rec)

    def _records_for(self, plant_id: Optional[str]) -> Iterable[NutrientDeliveryRecord]:
        """Return delivery records optionally filtered by ``plant_id``."""

        if plant_id is None:
            return self.delivery_log

        stored = self._log_by_plant.get(plant_id)
        actual_count = sum(1 for r in self.delivery_log if r.plant_id == plant_id)
        if stored is None or len(stored) != actual_count:
            stored = [r for r in self.delivery_log if r.plant_id == plant_id]
            self._log_by_plant[plant_id] = stored
        return stored

    def summarize_nutrients(self, plant_id: Optional[str] = None) -> Dict[str, float]:
        """Return total ppm delivered across all logged applications."""

        summary: Dict[str, float] = defaultdict(float)
        for record in self._records_for(plant_id):
            for element, ppm in record.ppm_delivered.items():
                summary[element] += ppm
        return dict(summary)

    def summarize_mg_for_day(self, date: datetime, plant_id: Optional[str] = None) -> Dict[str, float]:
        """Return total milligrams delivered on ``date``."""

        summary: Dict[str, float] = defaultdict(float)
        for record in self._records_for(plant_id):
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
        for record in self._records_for(plant_id):
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

    def summarize_daily_totals(
        self, plant_id: Optional[str] = None
    ) -> Dict[str, Dict[str, float]]:
        """Return milligram totals grouped by day."""

        daily: Dict[str, Dict[str, float]] = defaultdict(
            lambda: defaultdict(float)
        )
        for record in self._records_for(plant_id):
            key = record.timestamp.date().isoformat()
            for element, ppm in record.ppm_delivered.items():
                daily[key][element] += ppm * record.volume_l
        return {day: dict(values) for day, values in daily.items()}

    def calculate_remaining_requirements(
        self,
        plant_type: str,
        days: int,
        plant_id: Optional[str] = None,
        *,
        now: Optional[datetime] = None,
    ) -> Dict[str, float]:
        """Return unmet nutrient requirements for ``plant_type`` over ``days``.

        The calculation uses :func:`nutrient_requirements.get_requirements` to
        look up daily target values (in milligrams per plant). Logged
        applications for ``plant_id`` are summarized over the same period and
        subtracted from the targets. Only positive deficits are returned.
        """

        if days <= 0:
            raise ValueError("days must be positive")

        requirements = get_requirements(plant_type)
        if not requirements:
            return {}

        delivered = self.summarize_mg_since(days, plant_id, now=now)
        deficits: Dict[str, float] = {}
        target_span = {k: v * days for k, v in requirements.items()}
        for nutrient, total_needed in target_span.items():
            applied = delivered.get(nutrient, 0.0)
            remaining = round(total_needed - applied, 2)
            if remaining > 0:
                deficits[nutrient] = remaining
        return deficits


def register_fertilizers_from_dataset(
    tracker: "NutrientTracker",
    dataset_file: str = "fertilizers/fertilizer_products.json",
) -> None:
    """Load fertilizer product data and register nutrient profiles."""

    data = load_dataset(dataset_file)
    for product_id, info in data.items():
        if not isinstance(info, Mapping):
            continue
        ga = convert_guaranteed_analysis(info.get("guaranteed_analysis", {}))
        profile = ProductNutrientProfile(product_id=product_id)
        for element, fraction in ga.items():
            try:
                mg_per_kg = float(fraction) * 1_000_000
            except (TypeError, ValueError):
                continue
            profile.add_element(element, mg_per_kg)
        if profile.nutrient_map:
            tracker.register_product(profile)


__all__ = [
    "NutrientEntry",
    "ProductNutrientProfile",
    "NutrientDeliveryRecord",
    "NutrientTracker",
    "register_fertilizers_from_dataset",
]
