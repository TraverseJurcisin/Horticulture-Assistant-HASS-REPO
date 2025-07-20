from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class FertilizerRecommendation:
    product_name: str
    dose_rate: float
    dose_unit: str
    reason: str


@dataclass
class IrrigationRecommendation:
    volume_liters: float
    zones: List[str]
    justification: str


@dataclass
class RecommendationBundle:
    fertilizers: List[FertilizerRecommendation]
    irrigation: Optional[IrrigationRecommendation]
    notes: List[str]
    requires_approval: bool


class RecommendationEngine:
    def __init__(self):
        self.auto_approve = False
        self.plant_profiles = {}
        self.sensor_data = {}
        self.product_availability = {}
        self.ai_feedback = {}

    def set_auto_approve(self, value: bool):
        self.auto_approve = value

    def update_plant_profile(self, plant_id: str, profile_data: Dict):
        self.plant_profiles[plant_id] = profile_data

    def update_sensor_data(self, plant_id: str, sensor_payload: Dict):
        self.sensor_data[plant_id] = sensor_payload

    def update_product_availability(self, product_payload: Dict):
        self.product_availability = product_payload

    def update_ai_feedback(self, plant_id: str, ai_feedback: Dict):
        self.ai_feedback[plant_id] = ai_feedback

    def recommend(self, plant_id: str) -> RecommendationBundle:
        profile = self.plant_profiles.get(plant_id, {})
        sensors = self.sensor_data.get(plant_id, {})
        ai_notes = self.ai_feedback.get(plant_id, {})
        notes = []
        fert_recs = []

        # Example fertilizer recommendation
        if sensors.get("nitrate_ppm", 0) < profile.get("n_required_ppm", 0):
            best_nitrogen = self._select_best_product("N")
            if best_nitrogen:
                fert_recs.append(FertilizerRecommendation(
                    product_name=best_nitrogen,
                    dose_rate=5.0,
                    dose_unit="ml/L",
                    reason="Low nitrate level"
                ))

        # Example irrigation recommendation
        irrigation = None
        if sensors.get("vwc", 100) < profile.get("min_vwc", 30):
            irrigation = IrrigationRecommendation(
                volume_liters=2.0,
                zones=profile.get("zones", []),
                justification="Soil moisture below threshold"
            )

        requires_approval = not self.auto_approve
        if requires_approval:
            notes.append("Approval required for this recommendation bundle.")

        return RecommendationBundle(
            fertilizers=fert_recs,
            irrigation=irrigation,
            notes=notes + ai_notes.get("alerts", []),
            requires_approval=requires_approval
        )

    def _select_best_product(self, element: str) -> Optional[str]:
        for product in self.product_availability:
            if element in self.product_availability[product].get("elements", []):
                return product
        return None