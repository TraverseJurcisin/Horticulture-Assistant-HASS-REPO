from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import datetime
import json

@dataclass
class InferenceResult:
    plant_id: str
    recommendations: List[str]
    confidence: float
    flagged_issues: List[str]
    notes: Optional[str] = None

@dataclass
class DailyPackage:
    date: str
    plant_data: Dict[str, Any]
    environment_data: Dict[str, Any]
    fertigation_data: Dict[str, Any]
    notes: Optional[str] = None

class AIInferenceEngine:
    def __init__(self, auto_approve: bool = False):
        self.auto_approve = auto_approve
        self.history: List[InferenceResult] = []

    def analyze(self, package: DailyPackage) -> List[InferenceResult]:
        results = []
        for plant_id, data in package.plant_data.items():
            recs = []
            issues = []

            growth_rate = data.get("growth_rate")
            expected_growth = data.get("expected_growth")
            yield_obs = data.get("yield")
            yield_exp = data.get("expected_yield")

            if growth_rate is not None and expected_growth is not None:
                if growth_rate < 0.75 * expected_growth:
                    issues.append("Low growth rate detected")
                    recs.append("Evaluate nutrient delivery and light levels")

            if yield_obs is not None and yield_exp is not None:
                if yield_obs < 0.8 * yield_exp:
                    issues.append("Yield below expected threshold")
                    recs.append("Check fertigation accuracy and media saturation")

            ec = data.get("ec")
            if ec is not None and ec > 2.5:
                issues.append("High EC detected")
                recs.append("Consider flushing media")

            confidence = 1.0 - len(issues) * 0.1
            result = InferenceResult(
                plant_id=plant_id,
                recommendations=recs,
                confidence=max(confidence, 0.1),
                flagged_issues=issues,
                notes=f"Processed {datetime.datetime.now()}"
            )
            results.append(result)
            self.history.append(result)
        return results

    def export_results(self) -> str:
        return json.dumps([r.__dict__ for r in self.history], indent=2)