#!/usr/bin/env python3
"""Search the fertilizer dataset for matching products."""

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

from plant_engine.fertilizer_dataset_lookup import (
    get_product_analysis_by_number, search_products)


def _print_analysis(analysis: dict) -> None:
    """Pretty print a fertilizer analysis mapping."""
    print(json.dumps(analysis, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Search fertilizer dataset")
    parser.add_argument("query", help="search string or product number")
    parser.add_argument(
        "--number",
        action="store_true",
        help="treat query as product number instead of text",
    )
    parser.add_argument("--limit", type=int, default=10, help="maximum results to list")
    args = parser.parse_args(argv)

    if args.number:
        analysis = get_product_analysis_by_number(args.query)
        if not analysis:
            print("No matching product found")
            return
        _print_analysis(analysis)
        return

    matches = search_products(args.query, limit=args.limit)
    for name in matches:
        print(name)


if __name__ == "__main__":  # pragma: no cover
    main()
