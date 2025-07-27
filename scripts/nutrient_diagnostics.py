#!/usr/bin/env python3
"""Analyze nutrient levels for a crop stage."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.nutrient_analysis import analyze_nutrient_profile


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Analyze nutrient levels and report deficiencies/surplus"
    )
    parser.add_argument("plant_type", help="Crop identifier")
    parser.add_argument("stage", help="Growth stage")
    parser.add_argument(
        "levels",
        type=Path,
        help="Path to JSON file with current nutrient levels",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the analysis JSON",
    )
    args = parser.parse_args(argv)

    data = json.loads(args.levels.read_text())
    result = analyze_nutrient_profile(data, args.plant_type, args.stage)
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
