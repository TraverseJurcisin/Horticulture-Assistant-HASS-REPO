"""CLI wrapper for root zone calculations from :mod:`plant_engine.rootzone_model`."""

from __future__ import annotations

import argparse

from plant_engine.rootzone_model import (estimate_rootzone_depth,
                                         estimate_water_capacity)
from plant_engine.utils import load_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate root zone parameters")
    parser.add_argument("profile", help="Plant profile JSON")
    parser.add_argument("growth", help="Growth stats JSON")
    args = parser.parse_args()

    profile = load_json(args.profile)
    growth = load_json(args.growth)

    depth = estimate_rootzone_depth(profile, growth)
    zone = estimate_water_capacity(depth)
    result = zone.to_dict()
    import json

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
