"""Utility helpers for automation scripts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, Tuple


def iter_profiles(base_path: str) -> Iterable[Tuple[str, Dict]]:
    """Yield ``(plant_id, profile_data)`` from ``base_path`` JSON files."""
    path = Path(base_path)
    if not path.is_dir():
        return
    for file in path.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            plant_id = data.get("plant_id") or file.stem
            yield plant_id, data
        except Exception:
            continue


def append_json_log(log_path: Path, entry: Dict) -> None:
    """Append ``entry`` to a JSON list stored at ``log_path``."""
    log_path.parent.mkdir(exist_ok=True)
    log_entries = []
    if log_path.is_file():
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                val = json.load(f)
            if isinstance(val, list):
                log_entries = val
        except json.JSONDecodeError:
            pass
    log_entries.append(entry)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log_entries, f, indent=2)

