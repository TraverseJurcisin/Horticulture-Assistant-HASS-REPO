"""Simple engine for fertilizer and irrigation suggestions."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

from plant_engine.irrigation_manager import get_daily_irrigation_target
from plant_engine.environment_manager import generate_environment_alerts


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
    """Generate fertigation and irrigation suggestions for plants.

    The engine stores sensor readings and plant profiles then produces
    recommendations for irrigation volume and fertilizer dosing.  Product
    availability can be provided so that only stocked items are suggested.
    """

    def __init__(self) -> None:
        """Initialize empty state containers."""
        self.auto_approve = False
        self.plant_profiles: Dict[str, Dict] = {}
        self.sensor_data: Dict[str, Dict] = {}
        self.product_availability: Dict[str, Dict] = {}
        self.ai_feedback: Dict[str, Dict] = {}
        self.environment_data: Dict[str, Dict] = {}

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------

    def set_auto_approve(self, value: bool) -> None:
        """Enable or disable automatic approval of recommendations."""
        self.auto_approve = value

    def update_plant_profile(self, plant_id: str, profile_data: Dict) -> None:
        """Store profile information for ``plant_id``."""
        self.plant_profiles[plant_id] = profile_data

    def update_sensor_data(self, plant_id: str, sensor_payload: Dict) -> None:
        """Record the latest sensor payload for ``plant_id``."""
        self.sensor_data[plant_id] = sensor_payload

    def update_product_availability(self, product_payload: Dict) -> None:
        """Set the currently available fertilizer products."""
        self.product_availability = product_payload

    def update_ai_feedback(self, plant_id: str, ai_feedback: Dict) -> None:
        """Cache AI feedback notes for ``plant_id``."""
        self.ai_feedback[plant_id] = ai_feedback

    def update_environment_data(self, plant_id: str, env_payload: Dict) -> None:
        """Record latest environmental readings for ``plant_id``."""
        self.environment_data[plant_id] = env_payload

    # ------------------------------------------------------------------
    # Recommendation logic
    # ------------------------------------------------------------------

    @lru_cache(maxsize=None)
    def _get_irrigation_target(self, plant_type: str, stage: str) -> float:
        """Return daily irrigation volume (mL) for a plant stage."""
        if not plant_type or not stage:
            return 0.0
        return get_daily_irrigation_target(plant_type, stage)

    def _calculate_nutrient_deficits(self, plant_id: str) -> Dict[str, float]:
        """Return ppm deficits using dataset guidelines."""
        profile = self.plant_profiles.get(plant_id, {})
        plant_type = profile.get("plant_type")
        stage = profile.get("lifecycle_stage")
        if not plant_type or not stage:
            return {}
        sensors = self.sensor_data.get(plant_id, {})
        current = {
            "N": sensors.get("nitrate_ppm"),
            "P": sensors.get("phosphate_ppm"),
            "K": sensors.get("potassium_ppm"),
        }
        try:
            from plant_engine.nutrient_manager import calculate_all_deficiencies
        except Exception:
            return {}
        return calculate_all_deficiencies(current, plant_type, stage)

    def _generate_fertilizer_recs(self, plant_id: str) -> List[FertilizerRecommendation]:
        """Return fertilizer recommendations based on deficiencies."""
        deficits = self._calculate_nutrient_deficits(plant_id)
        recommendations: List[FertilizerRecommendation] = []
        for nutrient, deficit in deficits.items():
            product = self._select_best_product(nutrient)
            if not product:
                continue
            recommendations.append(
                FertilizerRecommendation(
                    product_name=product,
                    dose_rate=deficit,
                    dose_unit="ppm",
                    reason=f"{nutrient} deficit",
                )
            )
        return recommendations

    def recommend(self, plant_id: str) -> RecommendationBundle:
        """Return a bundle of fertilizer and irrigation suggestions."""
        profile = self.plant_profiles.get(plant_id, {})
        sensors = self.sensor_data.get(plant_id, {})
        ai_notes = self.ai_feedback.get(plant_id, {})
        notes: List[str] = []
        fert_recs = self._generate_fertilizer_recs(plant_id)

        # Basic irrigation recommendation
        irrigation = None
        if sensors.get("vwc", 100) < profile.get("min_vwc", 30):
            target_ml = self._get_irrigation_target(
                profile.get("plant_type", ""),
                profile.get("lifecycle_stage", ""),
            )
            irrigation = IrrigationRecommendation(
                volume_liters=target_ml / 1000.0,
                zones=profile.get("zones", []),
                justification="Soil moisture below threshold"
            )

        # Environment adjustment notes
        env = self.environment_data.get(plant_id)
        if env:
            alerts = generate_environment_alerts(
                env,
                profile.get("plant_type", ""),
                profile.get("lifecycle_stage"),
            )
            for msg in alerts.values():
                notes.append(msg)

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
        """Return the first product containing ``element`` if any."""
        return next(
            (
                name
                for name, data in self.product_availability.items()
                if element in data.get("elements", [])
            ),
            None,
        )
