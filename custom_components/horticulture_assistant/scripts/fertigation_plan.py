#!/usr/bin/env python3
"""Generate a fertigation plan for a crop stage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from ..engine.plant_engine.fertigation import generate_fertigation_plan


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate daily fertigation schedule for a plant stage"
    )
    parser.add_argument("plant_type", help="Crop identifier")
    parser.add_argument("stage", help="Growth stage")
    parser.add_argument("days", type=int, help="Number of days to generate")
    parser.add_argument("--output", type=Path, help="Optional path to write the plan JSON")
    args = parser.parse_args(argv)

    plan = generate_fertigation_plan(args.plant_type, args.stage, args.days)
    text = json.dumps(plan, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
