#!/usr/bin/env python3
"""Generate a pest management plan for a crop."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.pest_manager import build_pest_management_plan


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate pest management plan for specified pests"
    )
    parser.add_argument("plant_type", help="Crop identifier")
    parser.add_argument("pests", nargs="+", help="List of pest names")
    parser.add_argument("--output", type=Path, help="Optional path to write plan JSON")
    args = parser.parse_args(argv)

    plan = build_pest_management_plan(args.plant_type, args.pests)
    text = json.dumps(plan, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
