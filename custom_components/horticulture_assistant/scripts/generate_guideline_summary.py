"""Generate a consolidated guideline summary for a crop stage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

# Ensure project root on path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine import guidelines


def generate_summary(plant_type: str, stage: str | None = None) -> dict:
    """Return guideline summary for ``plant_type`` and optional ``stage``."""
    return guidelines.get_guideline_summary(plant_type, stage)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Show guideline summary for a plant stage"
    )
    parser.add_argument("plant_type", help="crop identifier")
    parser.add_argument("stage", nargs="?", default=None, help="growth stage")
    parser.add_argument(
        "--yaml", action="store_true", help="output YAML instead of JSON"
    )
    args = parser.parse_args(argv)

    data = generate_summary(args.plant_type, args.stage)
    if args.yaml:
        try:
            from io import StringIO
            from ruamel.yaml import YAML
        except Exception:  # pragma: no cover - optional dependency
            parser.error("ruamel.yaml required for --yaml output")
        yaml = YAML()
        yaml.default_flow_style = False
        yaml.sort_keys = False
        buf = StringIO()
        yaml.dump(data, buf)
        print(buf.getvalue())
    else:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
