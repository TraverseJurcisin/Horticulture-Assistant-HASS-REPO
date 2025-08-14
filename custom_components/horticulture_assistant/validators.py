from __future__ import annotations
from pathlib import Path
import json

try:
    from jsonschema import Draft202012Validator
except Exception:  # jsonschema is only needed for CI/tests/CLI
    Draft202012Validator = None  # type: ignore[assignment]

def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def validate_profile_dict(profile: dict, schema: dict) -> list[str]:
    """Return a list of human-readable errors (empty if valid)."""
    if Draft202012Validator is None:
        # If not installed in HA runtime, skip; CI/tests will install it
        return []
    validator = Draft202012Validator(schema)
    errors = []
    for e in validator.iter_errors(profile):
        loc = ".".join(str(x) for x in e.absolute_path) or "<root>"
        errors.append(f"{loc}: {e.message}")
    return errors

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
