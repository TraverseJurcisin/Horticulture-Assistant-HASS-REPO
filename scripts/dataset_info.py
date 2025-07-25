#!/usr/bin/env python3
"""List or search bundled datasets."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plant_engine.datasets import (
    list_datasets,
    list_dataset_info,
    search_datasets,
)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Dataset discovery utilities")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="list available dataset files")
    list_parser.add_argument(
        "--describe",
        action="store_true",
        help="include dataset descriptions in output",
    )

    search_parser = sub.add_parser("search", help="search dataset names")
    search_parser.add_argument("term", help="search term")

    args = parser.parse_args(argv)

    if args.command == "list":
        if args.describe:
            for name, desc in list_dataset_info().items():
                line = f"{name}: {desc}" if desc else name
                print(line)
        else:
            for name in list_datasets():
                print(name)
        return

    if args.command == "search":
        results = search_datasets(args.term)
        for name, desc in results.items():
            line = f"{name}: {desc}" if desc else name
            print(line)
        return


if __name__ == "__main__":  # pragma: no cover
    main()
