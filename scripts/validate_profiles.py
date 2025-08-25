#!/usr/bin/env python3
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "validators",
    ROOT / "custom_components" / "horticulture_assistant" / "validators.py",
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
validate_all_profiles = module.validate_all_profiles
schema = (
    ROOT / "custom_components" / "horticulture_assistant" / "schemas" / "plant_profile.schema.json"
)

dirs = [
    ROOT / "plants",
    ROOT / "data" / "local" / "plants",
]

issues = validate_all_profiles(dirs, schema)
if issues:
    print("Profile validation failed:")
    for i in issues:
        print(" -", i)
    sys.exit(1)

data_dir = (
    ROOT
    / "custom_components"
    / "horticulture_assistant"
    / "data"
    / "fertilizers"
    / "detail"
)

errors = 0
for path in data_dir.rglob("*.json"):
    text = path.read_text(encoding="utf-8")
    try:
        json.loads(text)
    except Exception as e:  # pragma: no cover - debug aid
        print(f"[JSON] {path}: {e}")
        errors += 1
    if not text.endswith("\n") or text.endswith("\n\n"):
        print(f"[EOL] {path}: file must end with exactly one newline")
        errors += 1

if errors:
    sys.exit(1)

print("Profile validation passed.")
