#!/usr/bin/env python3
"""Record a manual runoff EC reading for a plant."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from custom_components.horticulture_assistant.utils.ec_estimator import \
    log_runoff_ec


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Log a runoff EC measurement")
    parser.add_argument("plant_id", help="Plant identifier")
    parser.add_argument("ec", type=float, help="Runoff EC value in dS/m")
    parser.add_argument(
        "--base-path",
        help="Base directory containing plant logs",
        default=None,
    )
    args = parser.parse_args(argv)

    log_runoff_ec(args.plant_id, args.ec, base_path=args.base_path)
    print(f"Logged runoff EC {args.ec} for {args.plant_id}")


if __name__ == "__main__":  # pragma: no cover - manual use
    main()
