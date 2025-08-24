"""Train EC estimator coefficients from a CSV dataset."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from custom_components.horticulture_assistant.utils.ec_estimator import train_ec_model


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Train EC estimation model")
    parser.add_argument("csv_file", help="CSV file with training samples")
    parser.add_argument(
        "--output",
        help="Path to write trained model JSON",
        default=None,
    )
    parser.add_argument(
        "--plant-id",
        help="Plant ID to store model under plants/<id>/ec_model.json",
        default=None,
    )
    parser.add_argument(
        "--base-path",
        help="Base directory containing plant logs",
        default=None,
    )
    args = parser.parse_args(argv)

    samples = []
    with open(args.csv_file, newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            samples.append(row)

    model = train_ec_model(
        samples,
        output_path=args.output,
        plant_id=args.plant_id,
        base_path=args.base_path,
    )
    print(json.dumps(model.as_dict(), indent=2))


if __name__ == "__main__":  # pragma: no cover - manual use
    main()
