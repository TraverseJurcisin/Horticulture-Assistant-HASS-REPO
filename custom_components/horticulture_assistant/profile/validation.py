"""Profile-specific validation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..const import VARIABLE_SPECS


@dataclass(slots=True)
class ThresholdIssue:
    """Represents an out-of-bounds or inconsistent threshold value."""

    key: str
    code: str
    value: float | None
    floor: float | None
    ceiling: float | None
    unit: str | None
    other_key: str | None = None
    other_value: float | None = None

    def message(self) -> str:
        """Return a human readable summary."""

        value_str = _format_number(self.value)
        unit = f" {self.unit}" if self.unit else ""
        if self.code == "threshold_below_floor":
            floor = _format_number(self.floor)
            return f"{self.key}={value_str}{unit} is below the supported minimum {floor}{unit}."
        if self.code == "threshold_above_ceiling":
            ceiling = _format_number(self.ceiling)
            return f"{self.key}={value_str}{unit} exceeds the supported maximum {ceiling}{unit}."
        if self.code == "threshold_min_exceeds_max":
            other = _format_number(self.other_value)
            other_unit = unit
            return (
                f"{self.key}={value_str}{unit} is higher than {self.other_key}="
                f"{other}{other_unit}; ensure minimum values do not exceed maximum values."
            )
        return f"{self.key} has an invalid value."


def _format_number(value: float | None) -> str:
    if value is None:
        return "unknown"
    formatted = f"{value:.4f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_threshold_rules() -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for key, unit, _step, minimum, maximum in VARIABLE_SPECS:
        family = key.rsplit("_", 1)[0]
        rules[key] = {
            "family": family,
            "unit": unit,
            "floor": float(minimum) if minimum is not None else None,
            "ceiling": float(maximum) if maximum is not None else None,
        }

    alias_map = {
        "temperature_min": "temp_c_min",
        "temperature_max": "temp_c_max",
        "humidity_min": "rh_min",
        "humidity_max": "rh_max",
        "conductivity_min": "ec_min",
        "conductivity_max": "ec_max",
    }
    for alias, canonical in alias_map.items():
        if canonical not in rules:
            continue
        rules[alias] = dict(rules[canonical])

    # Manual illuminance bounds – stored in lux instead of mol/m²·d.
    rules.setdefault(
        "illuminance_min",
        {
            "family": "illuminance",
            "unit": "lx",
            "floor": 0.0,
            "ceiling": 250000.0,
        },
    )
    rules.setdefault(
        "illuminance_max",
        {
            "family": "illuminance",
            "unit": "lx",
            "floor": 0.0,
            "ceiling": 250000.0,
        },
    )

    return rules


_THRESHOLD_RULES = _build_threshold_rules()


def evaluate_threshold_bounds(thresholds: Mapping[str, Any]) -> list[ThresholdIssue]:
    """Return threshold issues detected in ``thresholds``."""

    issues: list[ThresholdIssue] = []
    family_map: dict[str, dict[str, tuple[str, float]]] = {}

    for key, raw in thresholds.items():
        rule = _THRESHOLD_RULES.get(key)
        if rule is None:
            continue
        value = _as_float(raw)
        if value is None:
            continue
        family = rule["family"]
        family_map.setdefault(family, {})[key] = (key, value)

        floor = rule.get("floor")
        ceiling = rule.get("ceiling")
        unit = rule.get("unit")

        if floor is not None and value < floor:
            issues.append(
                ThresholdIssue(
                    key=key,
                    code="threshold_below_floor",
                    value=value,
                    floor=floor,
                    ceiling=ceiling,
                    unit=unit,
                )
            )
        if ceiling is not None and value > ceiling:
            issues.append(
                ThresholdIssue(
                    key=key,
                    code="threshold_above_ceiling",
                    value=value,
                    floor=floor,
                    ceiling=ceiling,
                    unit=unit,
                )
            )

    for family, entries in family_map.items():
        min_entry = next(((k, v) for k, v in entries.values() if k.endswith("_min")), None)
        max_entry = next(((k, v) for k, v in entries.values() if k.endswith("_max")), None)
        if not min_entry or not max_entry:
            continue
        min_key, min_val = min_entry
        max_key, max_val = max_entry
        if min_val <= max_val:
            continue
        unit = _THRESHOLD_RULES.get(min_key, {}).get("unit")
        issues.append(
            ThresholdIssue(
                key=min_key,
                code="threshold_min_exceeds_max",
                value=min_val,
                floor=None,
                ceiling=None,
                unit=unit,
                other_key=max_key,
                other_value=max_val,
            )
        )
        issues.append(
            ThresholdIssue(
                key=max_key,
                code="threshold_min_exceeds_max",
                value=max_val,
                floor=None,
                ceiling=None,
                unit=unit,
                other_key=min_key,
                other_value=min_val,
            )
        )

    return issues


__all__ = ["ThresholdIssue", "evaluate_threshold_bounds"]
