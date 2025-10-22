#!/usr/bin/env python3
"""Validate run and harvest logs embedded in profile JSON files."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "custom_components" / "horticulture_assistant" / "data" / "schema"
PROFILE_DIRS = [
    ROOT / "plants",
    ROOT / "custom_components" / "horticulture_assistant" / "data" / "local" / "profiles",
    ROOT / "custom_components" / "horticulture_assistant" / "data" / "local" / "plants",
]


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _build_registry() -> Registry:
    resources: dict[str, Resource] = {}
    for schema_path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = _load_json(schema_path)
        resource = Resource.from_contents(schema)
        schema_id = schema.get("$id")
        if isinstance(schema_id, str) and schema_id:
            resources[schema_id] = resource
        resources[schema_path.as_uri()] = resource
    return Registry().with_resources(resources)


def _iter_profile_files() -> list[Path]:
    files: list[Path] = []
    for root in PROFILE_DIRS:
        if not root.exists():
            continue
        files.extend(sorted(root.rglob("*.json")))
    return files


def _format_error(prefix: str, error: jsonschema.ValidationError) -> str:
    location = ".".join(str(part) for part in error.absolute_path) or "<root>"
    return f"{prefix}{location}: {error.message}"


def main() -> int:
    registry = _build_registry()
    try:
        run_schema = _load_json(SCHEMA_DIR / "run_event.schema.json")
        harvest_schema = _load_json(SCHEMA_DIR / "harvest_event.schema.json")
    except FileNotFoundError as exc:
        print(f"Schema not found: {exc}")
        return 1

    run_validator = jsonschema.Draft202012Validator(run_schema, registry=registry)
    harvest_validator = jsonschema.Draft202012Validator(harvest_schema, registry=registry)

    issues: list[str] = []
    for profile_path in _iter_profile_files():
        try:
            payload = _load_json(profile_path)
        except Exception as exc:  # pragma: no cover - defensive logging
            issues.append(f"{profile_path}: invalid JSON ({exc})")
            continue

        for idx, event in enumerate(payload.get("run_history", []) or []):
            if not isinstance(event, dict):
                issues.append(f"{profile_path}: run_history[{idx}] must be an object")
                continue
            for error in run_validator.iter_errors(event):
                prefix = f"{profile_path}: run_history[{idx}]."
                issues.append(_format_error(prefix, error))

        for idx, event in enumerate(payload.get("harvest_history", []) or []):
            if not isinstance(event, dict):
                issues.append(f"{profile_path}: harvest_history[{idx}] must be an object")
                continue
            for error in harvest_validator.iter_errors(event):
                prefix = f"{profile_path}: harvest_history[{idx}]."
                issues.append(_format_error(prefix, error))

    if issues:
        print("Log validation failed:")
        for issue in issues:
            print(f" - {issue}")
        return 1

    print("Run and harvest logs validated successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
