"""CLI wrapper for root zone calculations from :mod:`plant_engine.rootzone_model`."""

from __future__ import annotations

import argparse
import json
from plant_engine.rootzone_model import estimate_rootzone_depth, estimate_water_capacity


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate root zone parameters")
    parser.add_argument("profile", help="Plant profile JSON")
    parser.add_argument("growth", help="Growth stats JSON")
    args = parser.parse_args()

    with open(args.profile, "r", encoding="utf-8") as f:
        profile = json.load(f)
    with open(args.growth, "r", encoding="utf-8") as f:
        growth = json.load(f)

    depth = estimate_rootzone_depth(profile, growth)
    zone = estimate_water_capacity(depth)
    result = zone.to_dict()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
