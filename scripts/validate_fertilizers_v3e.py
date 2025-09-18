#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import jsonschema
except Exception:
    print("Please `pip install jsonschema` (CI will install it).")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "custom_components" / "horticulture_assistant" / "data" / "fertilizers"
SCHEMA_PATH = DATA_DIR / "schema" / "2025-09-V3e.schema.json"

def iter_detail_files():
    detail_dir = DATA_DIR / "detail"
    if not detail_dir.exists():
        return []
    return sorted(detail_dir.rglob("*.json"))

def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)

def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"Schema not found: {SCHEMA_PATH}")
        return 0

    schema = load_json(SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)

    failures: list[tuple[Path, list[jsonschema.ValidationError]]] = []
    for detail_file in iter_detail_files():
        data = load_json(detail_file)
        errors = sorted(validator.iter_errors(data), key=lambda err: err.path)
        if errors:
            failures.append((detail_file, errors))

    if failures:
        print("Schema validation failures detected:")
        for path, errs in failures:
            print(f"\n# {path}")
            for err in errs:
                location = " -> ".join(map(str, err.path)) or "<root>"
                print(f"  • {location}: {err.message}")
        return 1

    print("All fertilizer JSON files conform to the 2025-09-V3e schema.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
