"""CLI helper using :func:`plant_engine.growth_model.update_growth_index`."""

from __future__ import annotations

import argparse
import json
from plant_engine.growth_model import update_growth_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Update plant VGI")
    parser.add_argument("plant_id")
    parser.add_argument("environment", help="Environment JSON")
    parser.add_argument("transpiration_ml", type=float)
    args = parser.parse_args()

    with open(args.environment, "r", encoding="utf-8") as f:
        env = json.load(f)

    result = update_growth_index(args.plant_id, env, args.transpiration_ml)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
