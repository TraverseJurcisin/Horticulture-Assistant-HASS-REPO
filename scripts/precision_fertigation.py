import argparse
import json
from pathlib import Path
import sys

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from plant_engine.fertigation import recommend_precise_fertigation_with_injection
import yaml


def load_water_profile(path: str) -> dict:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate precise fertigation plan")
    parser.add_argument("plant_type")
    parser.add_argument("stage")
    parser.add_argument("volume_l", type=float)
    parser.add_argument("--water-profile")
    parser.add_argument("--include-micro", action="store_true")
    parser.add_argument("--yaml", action="store_true", dest="as_yaml")
    args = parser.parse_args(argv)

    water = load_water_profile(args.water_profile) if args.water_profile else None

    fert_map = {
        "N": "foxfarm_grow_big",
        "P": "foxfarm_grow_big",
        "K": "intrepid_granular_potash_0_0_60",
    }

    schedule, total, breakdown, warnings, diag, injection = recommend_precise_fertigation_with_injection(
        args.plant_type,
        args.stage,
        args.volume_l,
        water,
        fertilizers=fert_map,
        include_micro=args.include_micro,
    )

    result = {
        "schedule": schedule,
        "cost_total": total,
        "cost_breakdown": breakdown,
        "warnings": warnings,
        "diagnostics": diag,
        "injection_volumes": injection,
    }

    if args.as_yaml:
        print(yaml.safe_dump(result, sort_keys=False))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":  # pragma: no cover
    main()
