"""Command line interface for :mod:`plant_engine.ai_model`."""

from __future__ import annotations

import argparse

from ..engine.plant_engine.ai_model import analyze
from ..engine.plant_engine.utils import load_json


def main() -> None:
    parser = argparse.ArgumentParser(description="Run AI threshold analysis")
    parser.add_argument("data", help="Path to JSON data for analysis")
    args = parser.parse_args()

    payload = load_json(args.data)

    result = analyze(payload)
    import json

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
