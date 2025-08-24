#!/usr/bin/env python3
"""Validate that all dataset files load correctly."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the Python path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.datasets import validate_all_datasets


def main(argv: list[str] | None = None) -> None:
    bad = validate_all_datasets()
    if bad:
        print("Invalid datasets:")
        for name in bad:
            print(name)
        sys.exit(1)
    print("All datasets valid")


if __name__ == "__main__":  # pragma: no cover
    main()
