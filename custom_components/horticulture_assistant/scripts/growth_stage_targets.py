#!/usr/bin/env python3
"""Output growth stage guidelines with environment and nutrient targets."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.growth_stage import growth_stage_summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Display growth stage durations with target guidelines"
    )
    parser.add_argument("plant_type", help="Plant type to summarize")
    parser.add_argument(
        "--start-date",
        help="Optional planting start date (YYYY-MM-DD) to include harvest prediction",
    )
    parser.add_argument("--yaml", action="store_true", help="Output YAML format")
    args = parser.parse_args(argv)

    start = date.fromisoformat(args.start_date) if args.start_date else None
    summary = growth_stage_summary(args.plant_type, start_date=start, include_guidelines=True)

    if args.yaml:
        import yaml

        print(yaml.safe_dump(summary, sort_keys=False))
    else:
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
