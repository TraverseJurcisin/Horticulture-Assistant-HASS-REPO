"""CLI for calculating nutrient deficits from totals."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root on sys.path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from custom_components.horticulture_assistant.utils.nutrient_requirements import (
    calculate_deficit,
)


def _load_totals(arg: str) -> dict:
    path = Path(arg)
    if path.is_file():
        return json.loads(path.read_text())
    return json.loads(arg)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Calculate nutrient deficit")
    parser.add_argument("plant_type", help="Plant type")
    parser.add_argument(
        "totals",
        help="JSON string or file with current nutrient totals",
    )
    args = parser.parse_args(argv)

    totals = _load_totals(args.totals)
    deficit = calculate_deficit(totals, args.plant_type)
    print(json.dumps(deficit, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
