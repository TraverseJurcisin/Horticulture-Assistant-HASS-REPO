"""CLI helper using :func:`plant_engine.growth_model.update_growth_index`."""

from __future__ import annotations

import argparse

from ..engine.plant_engine.growth_model import update_growth_index
from ..engine.plant_engine.utils import load_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Update plant VGI")
    parser.add_argument("plant_id")
    parser.add_argument("environment", help="Environment JSON")
    parser.add_argument("transpiration_ml", type=float)
    args = parser.parse_args()

    env = load_json(args.environment)

    result = update_growth_index(args.plant_id, env, args.transpiration_ml)
    import json

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
