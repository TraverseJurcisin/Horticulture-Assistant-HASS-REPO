#!/usr/bin/env python3
"""Generate a comprehensive cultivation plan for a crop stage."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
import sys

# Ensure project root on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.environment_manager import generate_stage_environment_plan
from plant_engine.fertigation import generate_fertigation_plan
from plant_engine.integrated_monitor import generate_integrated_monitoring_schedule


def generate_plan(
    plant_type: str,
    stage: str,
    days: int,
    start: date,
    events: int,
) -> dict:
    """Return combined environment, fertigation and monitoring plans."""

    env = generate_stage_environment_plan(plant_type).get(stage, {})
    fertigation = generate_fertigation_plan(plant_type, stage, days)
    monitoring = [
        d.isoformat()
        for d in generate_integrated_monitoring_schedule(
            plant_type, stage, start, events
        )
    ]

    return {
        "environment": env,
        "fertigation_schedule": fertigation,
        "monitoring_schedule": monitoring,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate environment, fertigation and monitoring plan"
    )
    parser.add_argument("plant_type", help="Crop identifier")
    parser.add_argument("stage", help="Growth stage")
    parser.add_argument("days", type=int, help="Fertigation schedule days")
    parser.add_argument("start", help="Monitoring start date YYYY-MM-DD")
    parser.add_argument("events", type=int, help="Number of monitoring events")
    parser.add_argument("--output", type=Path, help="Optional output path")
    args = parser.parse_args(argv)

    plan = generate_plan(
        args.plant_type,
        args.stage,
        args.days,
        date.fromisoformat(args.start),
        args.events,
    )

    text = json.dumps(plan, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    else:
        print(text)


if __name__ == "__main__":  # pragma: no cover
    main()
