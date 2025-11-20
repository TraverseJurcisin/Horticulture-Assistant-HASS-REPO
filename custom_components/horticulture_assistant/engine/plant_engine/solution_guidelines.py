from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass

from .utils import (list_dataset_entries, load_dataset, normalize_key,
                    parse_range)

DATA_FILE = "solution/solution_guidelines.json"

_DATA: dict[str, dict[str, Mapping[str, Iterable[float]]]] = load_dataset(DATA_FILE)


@dataclass(slots=True, frozen=True)
class SolutionGuidelines:
    ec: tuple[float, float] | None = None
    ph: tuple[float, float] | None = None
    temp_c: tuple[float, float] | None = None
    do_mg_l: tuple[float, float] | None = None

    def as_dict(self) -> dict[str, list[float]]:
        result: dict[str, list[float]] = {}
        for key, val in asdict(self).items():
            if val is not None:
                result[key] = [float(val[0]), float(val[1])]
        return result


def list_supported_plants() -> list[str]:
    """Return crop names with solution guidelines available."""
    return list_dataset_entries(_DATA)


def get_solution_guidelines(plant_type: str, stage: str) -> SolutionGuidelines:
    """Return nutrient solution parameter ranges for the plant stage."""
    data = _DATA.get(normalize_key(plant_type), {}).get(normalize_key(stage), {})
    if not isinstance(data, Mapping):
        data = {}
    return SolutionGuidelines(
        ec=parse_range(data.get("ec")),
        ph=parse_range(data.get("ph")),
        temp_c=parse_range(data.get("temp_c")),
        do_mg_l=parse_range(data.get("do_mg_l")),
    )


def evaluate_solution(readings: Mapping[str, float], plant_type: str, stage: str) -> dict[str, str]:
    """Return 'low' or 'high' indicators when readings fall outside ranges."""
    guide = get_solution_guidelines(plant_type, stage)
    result: dict[str, str] = {}
    if guide.ec is not None and "ec" in readings:
        if readings["ec"] < guide.ec[0]:
            result["ec"] = "low"
        elif readings["ec"] > guide.ec[1]:
            result["ec"] = "high"
    if guide.ph is not None and "ph" in readings:
        if readings["ph"] < guide.ph[0]:
            result["ph"] = "low"
        elif readings["ph"] > guide.ph[1]:
            result["ph"] = "high"
    if guide.temp_c is not None and "temp_c" in readings:
        if readings["temp_c"] < guide.temp_c[0]:
            result["temp_c"] = "low"
        elif readings["temp_c"] > guide.temp_c[1]:
            result["temp_c"] = "high"
    if guide.do_mg_l is not None and "do_mg_l" in readings:
        if readings["do_mg_l"] < guide.do_mg_l[0]:
            result["do_mg_l"] = "low"
        elif readings["do_mg_l"] > guide.do_mg_l[1]:
            result["do_mg_l"] = "high"
    return result


__all__ = [
    "SolutionGuidelines",
    "list_supported_plants",
    "get_solution_guidelines",
    "evaluate_solution",
]
