"""Simple engine for fertilizer and irrigation suggestions."""

from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache

from ..engine.plant_engine.environment_manager import generate_environment_alerts, optimize_environment
from ..engine.plant_engine.irrigation_manager import get_daily_irrigation_target


@cache
def _cached_irrigation_target(plant_type: str, stage: str) -> float:
    """Return cached daily irrigation target for a plant stage."""

    if not plant_type or not stage:
        return 0.0
    return get_daily_irrigation_target(plant_type, stage)


@dataclass
class FertilizerRecommendation:
    """Recommended fertilizer application for a nutrient deficit."""

    product_name: str
    dose_rate: float
    dose_unit: str
    reason: str
    severity: str | None = None


@dataclass
class IrrigationRecommendation:
    volume_liters: float
    zones: list[str]
    justification: str


@dataclass
class EnvironmentRecommendation:
    """Recommended environment adjustments and target setpoints."""

    adjustments: dict[str, str]
    setpoints: dict[str, float]


@dataclass
class RecommendationBundle:
    fertilizers: list[FertilizerRecommendation]
    irrigation: IrrigationRecommendation | None
    environment: EnvironmentRecommendation | None
    notes: list[str]
    requires_approval: bool


class RecommendationEngine:
    """Generate fertigation and irrigation suggestions for plants.

    The engine stores sensor readings and plant profiles then produces
    recommendations for irrigation volume and fertilizer dosing.  Product
    availability can be provided so that only stocked items are suggested.

    A small cache is maintained to quickly map nutrients to available
    fertilizer products so repeated recommendations run efficiently.
    """

    def __init__(self) -> None:
        """Initialize empty state containers."""
        self.auto_approve = False
        self.plant_profiles: dict[str, dict] = {}
        self.sensor_data: dict[str, dict] = {}
        self.product_availability: dict[str, dict] = {}
        self.ai_feedback: dict[str, dict] = {}
        self.environment_data: dict[str, dict] = {}
        # Internal mapping of nutrient element -> product id
        self._element_map: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Update helpers
    # ------------------------------------------------------------------

    def set_auto_approve(self, value: bool) -> None:
        """Enable or disable automatic approval of recommendations."""
        self.auto_approve = value

    def update_plant_profile(self, plant_id: str, profile_data: dict) -> None:
        """Store profile information for ``plant_id``."""
        self.plant_profiles[plant_id] = profile_data

    def update_sensor_data(self, plant_id: str, sensor_payload: dict) -> None:
        """Record the latest sensor payload for ``plant_id``."""
        self.sensor_data[plant_id] = sensor_payload

    def update_product_availability(self, product_payload: dict) -> None:
        """Set the currently available fertilizer products.

        The nutrient-to-product cache is rebuilt whenever availability changes
        to speed up subsequent lookups.
        """
        self.product_availability = product_payload
        self._refresh_element_map()

    def _refresh_element_map(self) -> None:
        """Rebuild the nutrient element lookup cache."""
        mapping: dict[str, str] = {}
        for pid, data in self.product_availability.items():
            for element in data.get("elements", []):
                mapping.setdefault(element, pid)
        self._element_map = mapping

    def reset_state(self) -> None:
        """Clear stored profiles, sensor data and cached mappings."""
        self.plant_profiles.clear()
        self.sensor_data.clear()
        self.product_availability.clear()
        self.ai_feedback.clear()
        self.environment_data.clear()
        self._element_map.clear()

    def recommend_all(self) -> dict[str, RecommendationBundle]:
        """Return recommendations for every known plant."""
        return {pid: self.recommend(pid) for pid in self.plant_profiles}

    def update_ai_feedback(self, plant_id: str, ai_feedback: dict) -> None:
        """Cache AI feedback notes for ``plant_id``."""
        self.ai_feedback[plant_id] = ai_feedback

    def update_environment_data(self, plant_id: str, env_payload: dict) -> None:
        """Record latest environmental readings for ``plant_id``."""
        self.environment_data[plant_id] = env_payload

    # ------------------------------------------------------------------
    # Recommendation logic
    # ------------------------------------------------------------------

    def _get_irrigation_target(self, plant_type: str, stage: str) -> float:
        """Return daily irrigation volume (mL) for a plant stage."""
        return _cached_irrigation_target(plant_type, stage)

    def _calculate_nutrient_deficits(self, plant_id: str) -> dict[str, float]:
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
            from ..engine.plant_engine.nutrient_manager import calculate_all_deficiencies
        except Exception:
            return {}
        return calculate_all_deficiencies(current, plant_type, stage)

    def _generate_environment_recs(self, plant_id: str) -> EnvironmentRecommendation | None:
        """Return environment optimization suggestions for ``plant_id``."""

        env = self.environment_data.get(plant_id)
        profile = self.plant_profiles.get(plant_id, {})
        plant_type = profile.get("plant_type")
        stage = profile.get("lifecycle_stage")
        if not env or not plant_type:
            return None

        try:
            result = optimize_environment(env, plant_type, stage)
            return EnvironmentRecommendation(
                adjustments=result.get("adjustments", {}),
                setpoints=result.get("setpoints", {}),
            )
        except Exception:
            return None

    def _generate_fertilizer_recs(self, plant_id: str) -> list[FertilizerRecommendation]:
        """Return fertilizer recommendations based on nutrient deficiencies."""

        deficits = self._calculate_nutrient_deficits(plant_id)
        if not deficits:
            return []

        # Assess deficiency severity for additional context in recommendations
        try:
            from ..engine.plant_engine.deficiency_manager import assess_deficiency_severity

            severity_map = assess_deficiency_severity(
                self.sensor_data.get(plant_id, {}),
                self.plant_profiles[plant_id].get("plant_type", ""),
                self.plant_profiles[plant_id].get("lifecycle_stage", ""),
            )
        except Exception:
            severity_map = {}

        recommendations: list[FertilizerRecommendation] = []
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
                    severity=severity_map.get(nutrient),
                )
            )
        return recommendations

    def recommend(self, plant_id: str) -> RecommendationBundle:
        """Return a bundle of fertilizer and irrigation suggestions."""
        profile = self.plant_profiles.get(plant_id, {})
        sensors = self.sensor_data.get(plant_id, {})
        ai_notes = self.ai_feedback.get(plant_id, {})
        notes: list[str] = []
        fert_recs = self._generate_fertilizer_recs(plant_id)
        env_rec = self._generate_environment_recs(plant_id)

        # Basic irrigation recommendation
        irrigation = None

        def _to_float(value: object, default: float | None = None) -> float | None:
            try:
                return float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return default

        current_vwc = _to_float(sensors.get("vwc"))
        min_vwc = _to_float(profile.get("min_vwc"), 30.0)
        if current_vwc is not None and min_vwc is not None and current_vwc < min_vwc:
            target_ml = self._get_irrigation_target(
                profile.get("plant_type", ""),
                profile.get("lifecycle_stage", ""),
            )
            irrigation = IrrigationRecommendation(
                volume_liters=target_ml / 1000.0,
                zones=profile.get("zones", []),
                justification="Soil moisture below threshold",
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

        raw_alerts = ai_notes.get("alerts", [])
        if isinstance(raw_alerts, str):
            alerts = [raw_alerts] if raw_alerts.strip() else []
        elif isinstance(raw_alerts, Iterable):
            alerts = [str(item).strip() for item in raw_alerts if str(item).strip()]
        else:
            alerts = []

        return RecommendationBundle(
            fertilizers=fert_recs,
            irrigation=irrigation,
            environment=env_rec,
            notes=notes + alerts,
            requires_approval=requires_approval,
        )

    def _select_best_product(self, element: str) -> str | None:
        """Return the first product containing ``element`` if any."""
        return self._element_map.get(element)
