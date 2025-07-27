#!/usr/bin/env python3
"""Recommend environment adjustments for a plant type and stage.

This CLI tool computes optimized environment setpoints and suggested actions
based on current sensor readings. Results are printed as JSON for easy
integration with automation workflows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.environment_manager import optimize_environment


def _load_env(arg: str) -> dict:
    """Return environment data from a JSON string or file path."""
    path = Path(arg)
    if path.is_file():
        return json.loads(path.read_text())
    return json.loads(arg)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Generate environment optimization recommendations"
    )
    parser.add_argument("plant_type", help="Plant type for guidelines")
    parser.add_argument("stage", help="Growth stage")
    parser.add_argument(
        "--env",
        required=True,
        help="JSON string or file containing current environment readings",
    )
    parser.add_argument("--zone", help="Optional climate zone for adjustments")
    args = parser.parse_args(argv)

    env = _load_env(args.env)

    result = optimize_environment(env, args.plant_type, args.stage, zone=args.zone)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
