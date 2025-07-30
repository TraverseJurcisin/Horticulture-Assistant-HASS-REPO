#!/usr/bin/env python3
"""Estimate crop profit using yield records and market prices."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.profit_estimator import estimate_profit, estimate_expected_profit


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Estimate crop profit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    actual = sub.add_parser("actual", help="Profit from recorded yield")
    actual.add_argument("plant_id", help="Plant identifier")
    actual.add_argument("plant_type", help="Crop type")
    actual.add_argument(
        "--cost", action="append", type=float, default=[], help="Additional cost"
    )

    exp = sub.add_parser("expected", help="Profit from yield estimate")
    exp.add_argument("plant_type", help="Crop type")
    exp.add_argument(
        "--extra-cost", action="append", type=float, default=[], help="Extra cost"
    )

    args = parser.parse_args(argv)

    if args.cmd == "actual":
        costs = {f"extra_{i+1}": c for i, c in enumerate(args.cost)}
        profit = estimate_profit(args.plant_id, args.plant_type, costs)
        print(profit)
        return

    if args.cmd == "expected":
        extras = {f"extra_{i+1}": c for i, c in enumerate(args.extra_cost)}
        profit = estimate_expected_profit(args.plant_type, extras)
        print("unknown" if profit is None else profit)
        return


if __name__ == "__main__":  # pragma: no cover
    main()
