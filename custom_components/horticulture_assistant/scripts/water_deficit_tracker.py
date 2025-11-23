"""CLI wrapper for :func:`plant_engine.water_deficit_tracker.update_water_balance`."""

from __future__ import annotations

import argparse
import json

from ..engine.plant_engine.water_deficit_tracker import update_water_balance


def main() -> None:
    parser = argparse.ArgumentParser(description="Update water balance log")
    parser.add_argument("plant_id")
    parser.add_argument("irrigation_ml", type=float)
    parser.add_argument("transpiration_ml", type=float)
    parser.add_argument("--storage", default="data/water_balance")
    args = parser.parse_args()

    result = update_water_balance(
        args.plant_id,
        args.irrigation_ml,
        args.transpiration_ml,
        storage_path=args.storage,
    )
    print(json.dumps(result.as_dict(), indent=2))


if __name__ == "__main__":
    main()
