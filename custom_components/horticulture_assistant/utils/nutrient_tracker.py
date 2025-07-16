from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

@dataclass
class NutrientEntry:
    element: str
    value_mg_per_kg: float
    source_compound: Optional[str] = None

@dataclass
class ProductNutrientProfile:
    product_id: str
    nutrient_map: Dict[str, NutrientEntry] = field(default_factory=dict)

    def add_element(self, element: str, value: float, source: Optional[str] = None):
        self.nutrient_map[element] = NutrientEntry(element, value, source)

    def get_ppm_from_dose(self, dose_g: float, solution_kg: float = 1.0) -> Dict[str, float]:
        ppm_map = {}
        for nutrient in self.nutrient_map.values():
            total_mg = dose_g * (nutrient.value_mg_per_kg / 1000)
            ppm = total_mg / solution_kg
            ppm_map[nutrient.element] = round(ppm, 4)
        return ppm_map

@dataclass
class NutrientDeliveryRecord:
    plant_id: str
    batch_id: str
    timestamp: datetime
    ppm_delivered: Dict[str, float]
    volume_l: float

@dataclass
class NutrientTracker:
    product_profiles: Dict[str, ProductNutrientProfile] = field(default_factory=dict)
    delivery_log: List[NutrientDeliveryRecord] = field(default_factory=list)

    def register_product(self, profile: ProductNutrientProfile):
        self.product_profiles[profile.product_id] = profile

    def log_delivery(self, plant_id: str, batch_id: str, product_id: str, dose_g: float, volume_l: float):
        if product_id not in self.product_profiles:
            raise ValueError(f"Unknown product_id {product_id}")
        profile = self.product_profiles[product_id]
        ppm_map = profile.get_ppm_from_dose(dose_g, volume_l)
        record = NutrientDeliveryRecord(
            plant_id=plant_id,
            batch_id=batch_id,
            timestamp=datetime.now(),
            ppm_delivered=ppm_map,
            volume_l=volume_l
        )
        self.delivery_log.append(record)

    def summarize_nutrients(self, plant_id: Optional[str] = None) -> Dict[str, float]:
        summary = {}
        for record in self.delivery_log:
            if plant_id and record.plant_id != plant_id:
                continue
            for element, ppm in record.ppm_delivered.items():
                summary[element] = summary.get(element, 0) + ppm
        return summary