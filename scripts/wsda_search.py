#!/usr/bin/env python3
"""Search the WSDA fertilizer database for matching products."""

from __future__ import annotations

import argparse
import json
from typing import List

from pathlib import Path
import sys

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plant_engine.wsda_lookup import (
    search_products,
    get_product_analysis_by_number,
    get_product_analysis_by_name,
)


def _print_analysis(analysis: dict) -> None:
    """Pretty print a fertilizer analysis mapping."""
    print(json.dumps(analysis, indent=2, sort_keys=True))


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Search WSDA fertilizer database")
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
