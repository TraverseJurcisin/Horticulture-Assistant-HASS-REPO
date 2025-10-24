from __future__ import annotations

import json
from collections.abc import Mapping
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


def _format_errors(validator_cls, payload: Mapping[str, Any], schema: Mapping[str, Any] | None) -> list[str]:
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


def validate_harvest_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a harvest event payload."""

    return _format_errors(_validator(), event, _bio_def("harvest_event"))


def validate_nutrient_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a nutrient application payload."""

    return _format_errors(_validator(), event, _bio_def("nutrient_event"))


def validate_cultivation_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a cultivation event payload."""

    return _format_errors(_validator(), event, _bio_def("cultivation_event"))


def validate_run_event_dict(event: Mapping[str, Any]) -> list[str]:
    """Return validation issues for a run lifecycle payload."""

    return _format_errors(_validator(), event, _bio_def("run_event"))


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
