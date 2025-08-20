#!/usr/bin/env python3
from pathlib import Path
import sys
import importlib.util

ROOT = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location(
    "validators",
    ROOT / "custom_components" / "horticulture_assistant" / "validators.py",
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
validate_all_profiles = module.validate_all_profiles
schema = ROOT / "schemas" / "plant_profile.schema.json"

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
print("Profile validation passed.")
