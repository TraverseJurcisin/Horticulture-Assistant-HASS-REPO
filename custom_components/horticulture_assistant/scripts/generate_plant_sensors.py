"""Utility for converting daily plant reports into template sensor YAML."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from itertools import repeat
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from custom_components.horticulture_assistant.utils.path_utils import data_path
from typing import Dict, Iterable, List

try:
    from ruamel.yaml import YAML

    yaml = YAML()
    yaml.default_flow_style = False
    yaml.sort_keys = False
except Exception:  # pragma: no cover - fallback when YAML lib is missing
    yaml = None

from custom_components.horticulture_assistant.utils.json_io import load_json


DEFAULT_OUTPUT_DIR = Path("templates/generated")
DEFAULT_REPORT_DIR = Path(data_path(None, "reports"))


@dataclass
class SensorTemplate:
    """Representation of a Home Assistant template sensor."""

    name: str
    unique_id: str
    state: object
    unit_of_measurement: str = ""
    device_class: str = ""


def _load_report(plant_id: str, report_dir: Path) -> Dict[str, object]:
    """Return parsed daily report for ``plant_id`` from ``report_dir``."""

    path = report_dir / f"{plant_id}.json"
    return load_json(str(path))


def _write_yaml(sensors: Iterable[SensorTemplate], out_path: Path) -> None:
    """Write ``sensors`` to ``out_path`` in YAML format."""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sensor_dicts = [asdict(s) for s in sensors]
    if yaml is not None:
        data = {"template": [{"sensor": sensor_dicts}]}
        with out_path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)
        return

    # Basic string-based writer as fallback
    with out_path.open("w", encoding="utf-8") as fh:
        fh.write("template:\n  - sensor:\n")
        for sensor in sensor_dicts:
            fh.write(f"      - name: \"{sensor['name']}\"\n")
            fh.write(f"        unique_id: {sensor['unique_id']}\n")
            fh.write(f"        state: \"{sensor['state']}\"\n")
            fh.write(
                f"        unit_of_measurement: \"{sensor.get('unit_of_measurement','')}\"\n"
            )
            fh.write(
                f"        device_class: \"{sensor.get('device_class','')}\"\n"
            )


def generate_template_yaml(
    plant_id: str,
    report_dir: Path = DEFAULT_REPORT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
) -> Path:
    """Generate YAML template sensors for ``plant_id`` and return path."""

    data = _load_report(plant_id, report_dir)

    sensors: List[SensorTemplate] = []

    # Add VGI and Transpiration
    growth = data.get("growth", {})
    sensors.append(
        SensorTemplate(
            name=f"{plant_id} VGI Today",
            unique_id=f"{plant_id}_vgi_today",
            state=growth.get("vgi_today", 0),
        )
    )
    sensors.append(
        SensorTemplate(
            name=f"{plant_id} VGI Total",
            unique_id=f"{plant_id}_vgi_total",
            state=growth.get("vgi_total", 0),
        )
    )

    sensors.append(
        SensorTemplate(
            name=f"{plant_id} Transpiration",
            unique_id=f"{plant_id}_transpiration",
            state=data.get("transpiration", {}).get("transpiration_ml_day", 0),
        )
    )

    water = data.get("water_deficit", {})
    sensors.append(
        SensorTemplate(
            name=f"{plant_id} Water Available",
            unique_id=f"{plant_id}_ml_available",
            state=water.get("ml_available", 0),
        )
    )
    sensors.append(
        SensorTemplate(
            name=f"{plant_id} Depletion %",
            unique_id=f"{plant_id}_depletion_pct",
            state=round(water.get("depletion_pct", 0) * 100, 2),
            unit_of_measurement="%",
        )
    )

    sensors.append(
        SensorTemplate(
            name=f"{plant_id} MAD Crossed",
            unique_id=f"{plant_id}_mad_crossed",
            state=str(water.get("mad_crossed", False)),
        )
    )

    # NUE sensors
    nue = data.get("nue", {}).get("nue", {})
    for element, value in nue.items():
        sensors.append(
            SensorTemplate(
                name=f"{plant_id} NUE {element}",
                unique_id=f"{plant_id}_nue_{element}",
                state=value,
            )
        )

    # Threshold sensors
    thresholds = data.get("thresholds", {})
    for element, value in thresholds.items():
        sensors.append(
            SensorTemplate(
                name=f"{plant_id} Target {element}",
                unique_id=f"{plant_id}_threshold_{element}",
                state=value,
            )
        )

    out_path = output_dir / f"{plant_id}_sensors.yaml"
    _write_yaml(sensors, out_path)

    print(f"✅ Generated template sensors for {plant_id} at {out_path}")
    return out_path


def generate_from_directory(
    report_dir: Path = DEFAULT_REPORT_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    workers: int | None = None,
) -> list[Path]:
    """Generate YAML templates for all reports in ``report_dir`` using threads."""

    reports = sorted(report_dir.glob("*.json"))
    plant_ids = [p.stem for p in reports]
    if workers is None:
        workers = min(32, (os.cpu_count() or 1))

    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(
            ex.map(
                generate_template_yaml,
                plant_ids,
                repeat(report_dir),
                repeat(output_dir),
            )
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate template sensors from daily reports"
    )
    parser.add_argument("plant_id", nargs="?", help="ID used for the daily report file")
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
    parser.add_argument(
        "--all",
        action="store_true",
        help="generate templates for all reports in the directory",
    )

    args = parser.parse_args()

    if args.all:
        generate_from_directory(args.reports, args.output)
        return
    if not args.plant_id:
        parser.error("plant_id is required unless --all is specified")
    generate_template_yaml(args.plant_id, args.reports, args.output)


if __name__ == "__main__":
    main()
