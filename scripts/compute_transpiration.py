"""CLI for :func:`plant_engine.compute_transpiration.compute_transpiration`."""

from __future__ import annotations

import argparse
import json
from plant_engine.compute_transpiration import compute_transpiration


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute transpiration metrics")
    parser.add_argument("profile", help="Path to plant profile JSON")
    parser.add_argument("environment", help="Path to environment data JSON")
    args = parser.parse_args()

    with open(args.profile, "r", encoding="utf-8") as f:
        profile = json.load(f)
    with open(args.environment, "r", encoding="utf-8") as f:
        env = json.load(f)

    result = compute_transpiration(profile, env)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
