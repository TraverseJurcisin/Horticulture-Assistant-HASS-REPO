"""Command line interface for :mod:`plant_engine.ai_model`."""
from __future__ import annotations

import argparse
import json

from plant_engine.ai_model import analyze


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI threshold analysis")
    parser.add_argument("data", help="Path to JSON data for analysis")
    args = parser.parse_args()

    with open(args.data, "r", encoding="utf-8") as fh:
        payload = json.load(fh)

    result = analyze(payload)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
