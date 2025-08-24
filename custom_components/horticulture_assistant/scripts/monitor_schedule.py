#!/usr/bin/env python3
"""Generate integrated pest and disease monitoring schedules."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.integrated_monitor import generate_integrated_monitoring_schedule


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate combined pest and disease monitoring schedule"
    )
    parser.add_argument("plant_type", help="Plant type identifier")
    parser.add_argument("stage", nargs="?", help="Growth stage", default=None)
    parser.add_argument("start", help="Start date YYYY-MM-DD")
    parser.add_argument("events", type=int, help="Number of events to return")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    args = parser.parse_args(argv)

    start_date = date.fromisoformat(args.start)
    schedule = generate_integrated_monitoring_schedule(
        args.plant_type, args.stage, start_date, args.events
    )

    if args.as_json:
        print(json.dumps([d.isoformat() for d in schedule]))
    else:
        for d in schedule:
            print(d.isoformat())


if __name__ == "__main__":  # pragma: no cover
    main()
