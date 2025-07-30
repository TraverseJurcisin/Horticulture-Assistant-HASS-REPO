#!/usr/bin/env python3
"""Display consolidated reference info for a plant type."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.reference_data import get_plant_overview


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Show nutrient, environment and pest reference data for a plant type"
    )
    parser.add_argument("plant_type", help="Crop identifier")
    parser.add_argument(
        "--output", type=Path, help="Optional path to write the overview JSON"
    )
    args = parser.parse_args(argv)

    overview = get_plant_overview(args.plant_type)
    text = json.dumps(overview, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
