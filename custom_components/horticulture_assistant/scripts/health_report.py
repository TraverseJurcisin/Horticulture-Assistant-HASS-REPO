#!/usr/bin/env python3
"""Generate a consolidated plant health report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root on path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.health_report import generate_health_report
from plant_engine.utils import load_data


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate plant health report")
    parser.add_argument("plant_type", help="Plant type identifier")
    parser.add_argument("stage", help="Growth stage")
    parser.add_argument("--env", type=Path, required=True, help="Path to environment readings file")
    parser.add_argument(
        "--nutrients", type=Path, required=True, help="Path to nutrient levels file"
    )
    parser.add_argument("--pests", help="Comma separated list of observed pests", default="")
    parser.add_argument("--diseases", help="Comma separated list of observed diseases", default="")
    parser.add_argument("--output", type=Path, help="Optional output file path")
    args = parser.parse_args(argv)

    env = load_data(str(args.env)) or {}
    nutrients = load_data(str(args.nutrients)) or {}
    pests = [p.strip() for p in args.pests.split(",") if p.strip()]
    diseases = [d.strip() for d in args.diseases.split(",") if d.strip()]

    report = generate_health_report(
        args.plant_type,
        args.stage,
        env,
        nutrients,
        pests=pests,
        diseases=diseases,
    )

    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
