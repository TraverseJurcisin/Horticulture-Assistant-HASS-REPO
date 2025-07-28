#!/usr/bin/env python3
"""List or search bundled datasets."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.datasets import (
    list_datasets,
    list_dataset_info,
    list_datasets_by_category,
    list_dataset_info_by_category,
    search_datasets,
    get_dataset_description,
    dataset_exists,
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

    cat_parser = sub.add_parser("categories", help="list datasets grouped by directory")
    cat_parser.add_argument(
        "--describe",
        action="store_true",
        help="include dataset descriptions in output",
    )

    desc_parser = sub.add_parser("describe", help="show dataset description")
    desc_parser.add_argument("name", help="dataset name")

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

    if args.command == "categories":
        if args.describe:
            groups = list_dataset_info_by_category()
            for cat, mapping in groups.items():
                print(f"[{cat}]")
                for name, desc in mapping.items():
                    line = f"  {name}: {desc}" if desc else f"  {name}"
                    print(line)
        else:
            groups = list_datasets_by_category()
            for cat, names in groups.items():
                print(f"[{cat}]")
                for name in names:
                    print(f"  {name}")
        return

    if args.command == "describe":
        if not dataset_exists(args.name):
            print("Dataset not found", file=sys.stderr)
            raise SystemExit(1)
        desc = get_dataset_description(args.name) or ""
        print(desc)
        return


if __name__ == "__main__":  # pragma: no cover
    main()
