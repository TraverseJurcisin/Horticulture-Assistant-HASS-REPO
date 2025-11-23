#!/usr/bin/env python3
"""Generate a pest management plan for a crop."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from ..engine.plant_engine.pest_manager import build_pest_management_plan


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate pest management plan for a crop",
    )
    parser.add_argument("plant_type", help="Plant type identifier")
    parser.add_argument(
        "pests",
        help="Comma separated list of pests to include in the plan",
    )
    args = parser.parse_args(argv)

    pest_list = [p.strip() for p in args.pests.split(",") if p.strip()]
    plan = build_pest_management_plan(args.plant_type, pest_list)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
