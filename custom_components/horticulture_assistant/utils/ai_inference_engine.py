"""Lightweight rule based inference engine used by tests.

This module simulates an ML driven recommendation system so the rest of the
project can be exercised without pulling in any heavy dependencies.  It
examines daily plant data and emits simple suggestions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import datetime as _dt
import json


@dataclass
class InferenceResult:
    """Result of :class:`AIInferenceEngine.analyze`."""

    plant_id: str
    recommendations: List[str]
    confidence: float
    flagged_issues: List[str]
    notes: Optional[str] = None


@dataclass
class DailyPackage:
    """Container for daily inference inputs."""

    date: str
    plant_data: Dict[str, Any]
    #: Mapping of plant_id to environment metrics (``temp_c``/``humidity_pct`` etc.)
    environment_data: Dict[str, Any]
    fertigation_data: Dict[str, Any]
    notes: Optional[str] = None


class AIInferenceEngine:
    """Very small rule based inference engine."""

    #: EC value considered problematic when exceeded.
    HIGH_EC_THRESHOLD = 2.5

    def __init__(self, auto_approve: bool = False) -> None:
        self.auto_approve = auto_approve
        self.history: List[InferenceResult] = []

    # ------------------------------------------------------------------
    # Core analysis
    # ------------------------------------------------------------------

    def analyze(self, package: DailyPackage) -> List[InferenceResult]:
        """Return inference results for all plants in ``package``."""

        results: List[InferenceResult] = []
        for plant_id, pdata in package.plant_data.items():
            recs: List[str] = []
            issues: List[str] = []

            self._check_growth(pdata, issues, recs)
            self._check_yield(pdata, issues, recs)
            self._check_ec(pdata, issues, recs)
            env = package.environment_data.get(plant_id, {})
            plant_type = pdata.get("plant_type", "default")
            self._check_environment(env, plant_type, issues, recs)

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

    def _check_growth(self, data: Mapping[str, Any], issues: List[str], recs: List[str]) -> None:
        growth = data.get("growth_rate")
        expected = data.get("expected_growth")
        if growth is not None and expected is not None:
            if growth < 0.75 * expected:
                issues.append("Low growth rate detected")
                recs.append("Evaluate nutrient delivery and light levels")

    def _check_yield(self, data: Mapping[str, Any], issues: List[str], recs: List[str]) -> None:
        observed = data.get("yield")
        expected = data.get("expected_yield")
        if observed is not None and expected is not None:
            if observed < 0.8 * expected:
                issues.append("Yield below expected threshold")
                recs.append("Check fertigation accuracy and media saturation")

    def _check_ec(self, data: Mapping[str, Any], issues: List[str], recs: List[str]) -> None:
        ec = data.get("ec")
        if ec is not None and ec > self.HIGH_EC_THRESHOLD:
            issues.append("High EC detected")
            recs.append("Consider flushing media")

    def _check_environment(
        self,
        env: Mapping[str, Any],
        plant_type: str,
        issues: List[str],
        recs: List[str],
    ) -> None:
        """Check temperature stress based on dataset thresholds."""

        if not env:
            return
        try:
            from plant_engine.environment_manager import (
                evaluate_heat_stress,
                evaluate_cold_stress,
            )
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

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def export_results(self) -> str:
        """Return the stored inference results as a JSON string."""

        return json.dumps([r.__dict__ for r in self.history], indent=2)

    def reset_history(self) -> None:
        """Clear stored inference results."""

        self.history.clear()

