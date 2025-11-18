"""Generate a precise fertigation plan with injection volumes."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

import yaml

from plant_engine.fertigation import \
    recommend_precise_fertigation_with_injection


def load_water_profile(path: str) -> dict:
    """Return water quality data from ``path`` if it exists.

    The file may contain JSON or YAML. An empty mapping is returned when
    the file does not exist or cannot be parsed.
    """

    file_path = Path(path)
    if not file_path.is_file():
        return {}
    try:
        text = file_path.read_text()
        if file_path.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(text) or {}
        return json.loads(text)
    except Exception:
        return {}


def main(argv: list[str] | None = None) -> None:
    """Entry point for the ``precision_fertigation.py`` script."""

    parser = argparse.ArgumentParser(description="Generate precise fertigation plan")
    parser.add_argument("plant_type")
    parser.add_argument("stage")
    parser.add_argument("volume_l", type=float)
    parser.add_argument("--water-profile")
    parser.add_argument("--include-micro", action="store_true")
    parser.add_argument(
        "--use-synergy",
        action="store_true",
        help="Apply nutrient synergy adjustments",
    )
    parser.add_argument(
        "--use-stock-recipe", action="store_true", help="Include preset stock solution ratios"
    )
    parser.add_argument("--yaml", action="store_true", dest="as_yaml")
    args = parser.parse_args(argv)

    water = load_water_profile(args.water_profile) if args.water_profile else None

    fert_map = {
        "N": "foxfarm_grow_big",
        "P": "foxfarm_grow_big",
        "K": "intrepid_granular_potash_0_0_60",
    }

    result = recommend_precise_fertigation_with_injection(
        args.plant_type,
        args.stage,
        args.volume_l,
        water,
        fertilizers=fert_map,
        include_micro=args.include_micro,
        use_synergy=args.use_synergy,
    )

    recipe_injection = None
    if args.use_stock_recipe:
        from plant_engine.fertigation import apply_stock_solution_recipe

        recipe_injection = apply_stock_solution_recipe(
            args.plant_type,
            args.stage,
            args.volume_l,
        )

    payload = {
        "schedule": result.schedule,
        "cost_total": result.cost_total,
        "cost_breakdown": result.cost_breakdown,
        "warnings": result.warnings,
        "diagnostics": result.diagnostics,
        "injection_volumes": result.injection_volumes,
        "recipe_injection": recipe_injection,
    }

    if args.as_yaml:
        print(yaml.safe_dump(payload, sort_keys=False))
    else:
        print(json.dumps(payload, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
