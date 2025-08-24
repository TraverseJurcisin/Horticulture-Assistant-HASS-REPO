"""CLI for :func:`plant_engine.compute_transpiration.compute_transpiration`."""

from __future__ import annotations

import argparse

from plant_engine.compute_transpiration import compute_transpiration
from plant_engine.utils import load_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute transpiration metrics")
    parser.add_argument("profile", help="Path to plant profile JSON")
    parser.add_argument("environment", help="Path to environment data JSON")
    args = parser.parse_args()

    profile = load_json(args.profile)
    env = load_json(args.environment)

    result = compute_transpiration(profile, env)
    import json

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
