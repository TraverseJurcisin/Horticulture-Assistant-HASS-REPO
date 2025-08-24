"""Command line wrapper for :mod:`plant_engine.nutrient_efficiency`."""

from __future__ import annotations

import argparse

from plant_engine.nutrient_efficiency import calculate_nue


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate nutrient use efficiency")
    parser.add_argument("plant_id", help="ID of the plant")
    args = parser.parse_args()
    result = calculate_nue(args.plant_id)
    print(result)


if __name__ == "__main__":
    main()
