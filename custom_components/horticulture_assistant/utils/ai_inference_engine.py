"""Lightweight rule based inference engine used by tests.

This module simulates an ML driven recommendation system so the rest of the
project can be exercised without pulling in any heavy dependencies.  It
examines daily plant data and emits simple suggestions.
"""

from __future__ import annotations

import datetime as _dt
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class InferenceResult:
    """Result of :class:`AIInferenceEngine.analyze`."""

    plant_id: str
    recommendations: list[str]
    confidence: float
    flagged_issues: list[str]
    notes: str | None = None


@dataclass(slots=True)
class DailyPackage:
    """Container for daily inference inputs."""

    date: str
    plant_data: dict[str, Any]
    #: Mapping of plant_id to environment metrics (``temp_c``/``humidity_pct`` etc.)
    environment_data: dict[str, Any]
    fertigation_data: dict[str, Any]
    notes: str | None = None


class AIInferenceEngine:
    """Very small rule based inference engine."""

    #: EC value considered problematic when exceeded.
    HIGH_EC_THRESHOLD = 2.5

    def __init__(self, auto_approve: bool = False) -> None:
        self.auto_approve = auto_approve
        self.history: list[InferenceResult] = []

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    def analyze(self, package: DailyPackage) -> list[InferenceResult]:
        """Return inference results for all plants in ``package``."""

        results: list[InferenceResult] = []
        for plant_id, pdata in package.plant_data.items():
            recs: list[str] = []
            issues: list[str] = []

            self._check_growth(pdata, issues, recs)
            self._check_yield(pdata, issues, recs)
            self._check_ec(pdata, issues, recs)
            env = package.environment_data.get(plant_id, {})
            plant_type = pdata.get("plant_type", "default")
            stage = pdata.get("stage")

            self._check_environment(env, plant_type, issues, recs)
            self._check_environment_range(env, plant_type, issues, recs)
            fert = package.fertigation_data.get(plant_id)
            if fert:
                self._check_nutrient_levels(fert, plant_type, stage, issues, recs)
            self._check_pest_risk(env, plant_type, issues, recs)

            confidence = max(0.1, 1.0 - len(issues) * 0.1)
            results.append(
                InferenceResult(
                    plant_id=plant_id,
                    recommendations=recs,
                    confidence=confidence,
                    flagged_issues=issues,
                    notes=f"Processed {_dt.datetime.now().isoformat()}",
                )
            )
            self.history.append(results[-1])
        return results

    # ------------------------------------------------------------------
    # Individual checks
    # ------------------------------------------------------------------

    def _check_growth(self, data: Mapping[str, Any], issues: list[str], recs: list[str]) -> None:
        growth = data.get("growth_rate")
        expected = data.get("expected_growth")
        if growth is not None and expected is not None and growth < 0.75 * expected:
            issues.append("Low growth rate detected")
            recs.append("Evaluate nutrient delivery and light levels")

    def _check_yield(self, data: Mapping[str, Any], issues: list[str], recs: list[str]) -> None:
        observed = data.get("yield")
        expected = data.get("expected_yield")
        if observed is not None and expected is not None and observed < 0.8 * expected:
            issues.append("Yield below expected threshold")
            recs.append("Check fertigation accuracy and media saturation")

    def _check_ec(self, data: Mapping[str, Any], issues: list[str], recs: list[str]) -> None:
        ec = data.get("ec")
        if ec is not None and ec > self.HIGH_EC_THRESHOLD:
            issues.append("High EC detected")
            recs.append("Consider flushing media")

    def _check_environment(
        self,
        env: Mapping[str, Any],
        plant_type: str,
        issues: list[str],
        recs: list[str],
    ) -> None:
        """Check temperature stress based on dataset thresholds."""

        if not env:
            return
        try:
            from plant_engine.environment_manager import evaluate_cold_stress, evaluate_heat_stress
        except Exception:
            return

        temp = env.get("temp_c")
        rh = env.get("humidity_pct")
        if evaluate_heat_stress(temp, rh, plant_type):
            issues.append("Heat stress detected")
            recs.append("Increase cooling or shading")
        if evaluate_cold_stress(temp, plant_type):
            issues.append("Cold stress detected")
            recs.append("Provide heating or protection")

    def _check_environment_range(
        self,
        env: Mapping[str, Any],
        plant_type: str,
        issues: list[str],
        recs: list[str],
    ) -> None:
        """Flag readings outside recommended ranges."""

        if not env or not plant_type:
            return
        try:
            from plant_engine.environment_manager import compare_environment, get_environmental_targets
        except Exception:  # pragma: no cover - optional dependency
            return

        targets = get_environmental_targets(plant_type)
        if not targets:
            return

        comparison = compare_environment(env, targets)
        for key, status in comparison.items():
            if status == "within range":
                continue
            issues.append(f"{key} {status.replace('_', ' ')}")
            action = "increase" if status == "below range" else "decrease"
            recs.append(f"{action} {key}")

    def _check_pest_risk(
        self,
        env: Mapping[str, Any],
        plant_type: str,
        issues: list[str],
        recs: list[str],
    ) -> None:
        """Append pest risk warnings based on current environment."""

        if not env or not plant_type:
            return
        try:
            from plant_engine.pest_monitor import estimate_adjusted_pest_risk
        except Exception:  # pragma: no cover - optional dependency
            return

        risk = estimate_adjusted_pest_risk(plant_type, env)
        if not risk:
            return

        for pest, level in risk.items():
            if level in {"high", "moderate"}:
                issues.append(f"Potential {pest} outbreak: {level}")
                recs.append(f"Monitor for {pest} ({level} risk)")

    def _check_nutrient_levels(
        self,
        current: Mapping[str, Any],
        plant_type: str,
        stage: str | None,
        issues: list[str],
        recs: list[str],
    ) -> None:
        """Flag nutrient deficiencies using dataset guidelines."""

        if not current or not plant_type or not stage:
            return
        try:
            from plant_engine.nutrient_manager import calculate_deficiencies
        except Exception:  # pragma: no cover - optional dependency
            return

        deficits = calculate_deficiencies(current, plant_type, stage)
        for nutrient, amount in deficits.items():
            issues.append(f"{nutrient} deficiency {amount}ppm")
            recs.append(f"Add {amount}ppm {nutrient}")

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def export_results(self) -> str:
        """Return the stored inference results as a JSON string."""

        return json.dumps([asdict(r) for r in self.history], indent=2)

    def reset_history(self) -> None:
        """Clear stored inference results."""

        self.history.clear()
