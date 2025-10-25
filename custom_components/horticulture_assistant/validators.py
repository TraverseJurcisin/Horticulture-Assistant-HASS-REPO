from __future__ import annotations

import datetime as dt
import json
from collections.abc import Mapping, Sequence
from datetime import UTC
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from jsonschema import Draft202012Validator
except Exception:  # jsonschema is only needed for CI/tests/CLI
    Draft202012Validator = None  # type: ignore[assignment]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _validator() -> type[Draft202012Validator] | None:
    if Draft202012Validator is None:  # pragma: no cover - exercised in HA runtime
        return None
    return Draft202012Validator


def _format_errors(
    validator_cls,
    payload: Mapping[str, Any],
    schema: Mapping[str, Any] | None,
) -> list[str]:
    if validator_cls is None or schema is None:
        return []
    validator = validator_cls(schema)
    issues: list[str] = []
    for err in validator.iter_errors(payload):
        location = ".".join(str(part) for part in err.absolute_path) or "<root>"
        issues.append(f"{location}: {err.message}")
    return issues


def validate_profile_dict(profile: Mapping[str, Any], schema: Mapping[str, Any]) -> list[str]:
    """Return a list of human-readable errors (empty if valid)."""

    return _format_errors(_validator(), profile, schema)


@lru_cache(maxsize=1)
def _bio_schema() -> dict[str, Any]:
    from . import __path__

    base = Path(list(__path__)[0])  # type: ignore[index]
    return _load_json(base / "data" / "schema" / "bio_profile.schema.json")


def _bio_def(name: str) -> Mapping[str, Any] | None:
    schema = _bio_schema()
    return schema.get("$defs", {}).get(name)


def _require_string(event: Mapping[str, Any], key: str, *, allow_empty: bool = False) -> list[str]:
    value = event.get(key)
    if value is None:
        return [f"{key}: missing required value"]
    if not isinstance(value, str):
        value = str(value)
    if not allow_empty and not value.strip():
        return [f"{key}: missing required value"]
    return []


def _ensure_mapping(event: Mapping[str, Any], key: str) -> list[str]:
    value = event.get(key)
    if value is None:
        return []
    if isinstance(value, Mapping):
        return []
    return [f"{key}: expected an object"]


def _ensure_sequence_of_strings(event: Mapping[str, Any], key: str) -> list[str]:
    value = event.get(key)
    if value is None:
        return []
    if isinstance(value, set | frozenset):
        if any(not isinstance(item, str) for item in value):
            return [f"{key}: expected all items to be strings"]
        return []
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        non_strings = [item for item in value if not isinstance(item, str)]
        if non_strings:
            return [f"{key}: expected all items to be strings"]
        return []
    return [f"{key}: expected a list of strings"]


def _ensure_number(
    event: Mapping[str, Any],
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    integer: bool = False,
) -> list[str]:
    value = event.get(key)
    if value is None:
        return []
    try:
        number = float(value)
    except (TypeError, ValueError):
        return [f"{key}: expected a number"]
    if minimum is not None and number < minimum:
        return [f"{key}: must be ≥ {minimum}"]
    if maximum is not None and number > maximum:
        return [f"{key}: must be ≤ {maximum}"]
    if integer and abs(number - round(number)) > 1e-9:
        return [f"{key}: expected an integer"]
    return []


def _ensure_timestamp(event: Mapping[str, Any], key: str) -> list[str]:
    value = event.get(key)
    if value is None:
        return [f"{key}: missing required ISO-8601 timestamp"]
    text = str(value).strip()
    if not text:
        return [f"{key}: missing required ISO-8601 timestamp"]
    try:
        ts = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return [f"{key}: expected an ISO-8601 timestamp"]
    if ts.tzinfo is None:
        return [f"{key}: expected an ISO-8601 timestamp with timezone"]
    try:
        ts.astimezone(UTC)
    except Exception:  # pragma: no cover - defensive
        return [f"{key}: expected an ISO-8601 timestamp with timezone"]
    return []


def _manual_run_event_checks(event: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    issues.extend(_require_string(event, "run_id"))
    issues.extend(_require_string(event, "profile_id"))
    issues.extend(_ensure_timestamp(event, "started_at"))
    issues.extend(_ensure_mapping(event, "environment"))
    issues.extend(_ensure_mapping(event, "metadata"))
    issues.extend(_ensure_number(event, "targets_met", minimum=0.0))
    issues.extend(_ensure_number(event, "targets_total", minimum=0.0))
    issues.extend(_ensure_number(event, "success_rate", minimum=0.0, maximum=1.0))
    issues.extend(_ensure_number(event, "stress_events", minimum=0.0, integer=True))
    return issues


def _manual_harvest_event_checks(event: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    issues.extend(_require_string(event, "harvest_id"))
    issues.extend(_require_string(event, "profile_id"))
    issues.extend(_ensure_timestamp(event, "harvested_at"))
    issues.extend(_ensure_number(event, "yield_grams", minimum=0.0))
    issues.extend(_ensure_number(event, "area_m2", minimum=0.0))
    issues.extend(_ensure_number(event, "wet_weight_grams", minimum=0.0))
    issues.extend(_ensure_number(event, "dry_weight_grams", minimum=0.0))
    issues.extend(_ensure_number(event, "fruit_count", minimum=0.0, integer=True))
    issues.extend(_ensure_mapping(event, "metadata"))
    return issues


def _manual_nutrient_event_checks(event: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    issues.extend(_require_string(event, "event_id"))
    issues.extend(_require_string(event, "profile_id"))
    issues.extend(_ensure_timestamp(event, "applied_at"))
    issues.extend(_ensure_number(event, "solution_volume_liters", minimum=0.0))
    issues.extend(_ensure_number(event, "concentration_ppm", minimum=0.0))
    issues.extend(_ensure_number(event, "ec_ms", minimum=0.0))
    issues.extend(_ensure_number(event, "ph", minimum=0.0, maximum=14.0))
    additives = event.get("additives")
    if additives is not None:
        if isinstance(additives, set | frozenset):
            if any(not isinstance(item, str) for item in additives):
                issues.append("additives: expected all items to be strings")
            else:
                issues.append("additives: convert to list for stable ordering")
        elif isinstance(additives, Sequence) and not isinstance(additives, str | bytes | bytearray):
            if any(not isinstance(item, str) for item in additives):
                issues.append("additives: expected all items to be strings")
        else:
            issues.append("additives: expected a list of strings")
    issues.extend(_ensure_mapping(event, "metadata"))
    return issues


def _manual_cultivation_event_checks(event: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    issues.extend(_require_string(event, "event_id"))
    issues.extend(_require_string(event, "profile_id"))
    issues.extend(_ensure_timestamp(event, "occurred_at"))
    issues.extend(_require_string(event, "event_type"))
    issues.extend(_ensure_number(event, "metric_value"))
    issues.extend(_ensure_mapping(event, "metadata"))
    issues.extend(_ensure_sequence_of_strings(event, "tags"))
    return issues


def validate_harvest_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a harvest event payload."""
    issues = _manual_harvest_event_checks(event)
    issues.extend(_format_errors(_validator(), event, _bio_def("harvest_event")))
    return issues


def validate_nutrient_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a nutrient application payload."""
    issues = _manual_nutrient_event_checks(event)
    issues.extend(_format_errors(_validator(), event, _bio_def("nutrient_event")))
    return issues


def validate_cultivation_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a cultivation event payload."""
    issues = _manual_cultivation_event_checks(event)
    issues.extend(_format_errors(_validator(), event, _bio_def("cultivation_event")))
    return issues


def validate_run_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a run lifecycle payload."""
    issues = _manual_run_event_checks(event)
    issues.extend(_format_errors(_validator(), event, _bio_def("run_event")))
    return issues


def validate_all_profiles(root_dirs: list[Path], schema_path: Path) -> list[str]:
    """Validate all *.json profiles in the provided directories."""
    schema = _load_json(schema_path)
    issues: list[str] = []
    for root in root_dirs:
        if not root.exists():
            continue
        for p in root.rglob("*.json"):
            try:
                data = _load_json(p)
            except Exception as exc:
                issues.append(f"{p}: invalid JSON ({exc})")
                continue
            errs = validate_profile_dict(data, schema)
            issues.extend([f"{p}: {msg}" for msg in errs])
    return issues
