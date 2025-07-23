"""Utility for converting daily plant reports into template sensor YAML."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable


DEFAULT_OUTPUT_DIR = Path("templates/generated")
DEFAULT_REPORT_DIR = Path("data/reports")


def _load_report(plant_id: str, report_dir: Path) -> Dict[str, object]:
    """Return parsed daily report for ``plant_id`` from ``report_dir``."""

    path = report_dir / f"{plant_id}.json"
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_yaml(sensors: Iterable[Dict[str, object]], out_path: Path) -> None:
    """Write a list of ``sensors`` to ``out_path`` in YAML format."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write("template:\n  - sensor:\n")
        for sensor in sensors:
            fh.write(f"      - name: \"{sensor['name']}\"\n")
            fh.write(f"        unique_id: {sensor['unique_id']}\n")
            fh.write(f"        state: \"{sensor['state']}\"\n")
            fh.write("        unit_of_measurement: \"\"\n")
            fh.write("        device_class: \"\"\n")


def generate_template_yaml(
    plant_id: str,
    report_dir: Path = DEFAULT_REPORT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """Generate YAML template sensors for ``plant_id`` and return path."""

    data = _load_report(plant_id, report_dir)
    
    sensors = []

    # Add VGI and Transpiration
    growth = data.get("growth", {})
    sensors.append({
        "name": f"{plant_id} VGI Today",
        "unique_id": f"{plant_id}_vgi_today",
        "state": growth.get("vgi_today", 0)
    })
    sensors.append({
        "name": f"{plant_id} VGI Total",
        "unique_id": f"{plant_id}_vgi_total",
        "state": growth.get("vgi_total", 0)
    })

    sensors.append({
        "name": f"{plant_id} Transpiration",
        "unique_id": f"{plant_id}_transpiration",
        "state": data.get("transpiration", {}).get("transpiration_ml_day", 0)
    })

    water = data.get("water_deficit", {})
    sensors.append({
        "name": f"{plant_id} Water Available",
        "unique_id": f"{plant_id}_ml_available",
        "state": water.get("ml_available", 0)
    })
    sensors.append({
        "name": f"{plant_id} Depletion %",
        "unique_id": f"{plant_id}_depletion_pct",
        "state": round(water.get("depletion_pct", 0) * 100, 2)
    })

    sensors.append({
        "name": f"{plant_id} MAD Crossed",
        "unique_id": f"{plant_id}_mad_crossed",
        "state": str(water.get("mad_crossed", False))
    })

    # NUE sensors
    nue = data.get("nue", {}).get("nue", {})
    for element, value in nue.items():
        sensors.append({
            "name": f"{plant_id} NUE {element}",
            "unique_id": f"{plant_id}_nue_{element}",
            "state": value
        })

    # Threshold sensors
    thresholds = data.get("thresholds", {})
    for element, value in thresholds.items():
        sensors.append({
            "name": f"{plant_id} Target {element}",
            "unique_id": f"{plant_id}_threshold_{element}",
            "state": value
        })

    out_path = output_dir / f"{plant_id}_sensors.yaml"
    _write_yaml(sensors, out_path)

    print(f"✅ Generated template sensors for {plant_id} at {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate template sensors from daily reports")
    parser.add_argument("plant_id", help="ID used for the daily report file")
    parser.add_argument(
        "--reports",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="directory containing daily reports",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="directory to write generated YAML",
    )

    args = parser.parse_args()
    generate_template_yaml(args.plant_id, args.reports, args.output)


if __name__ == "__main__":
    main()
