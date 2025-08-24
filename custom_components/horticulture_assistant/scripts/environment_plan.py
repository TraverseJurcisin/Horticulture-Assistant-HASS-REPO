#!/usr/bin/env python3
"""Generate environment setpoint plans for a plant type."""

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

from plant_engine.environment_manager import (
    generate_stage_environment_plan,
    generate_zone_environment_plan,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate recommended environment setpoints for each growth stage"
    )
    parser.add_argument("plant_type", help="Plant type to generate the plan for")
    parser.add_argument(
        "--zone",
        help="Optional climate zone to adjust recommendations",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the plan JSON",
    )
    args = parser.parse_args(argv)

    if args.zone:
        plan = generate_zone_environment_plan(args.plant_type, args.zone)
    else:
        plan = generate_stage_environment_plan(args.plant_type)

    text = json.dumps(plan, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
