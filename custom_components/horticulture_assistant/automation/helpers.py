"""Utility helpers for automation scripts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from ..utils.json_io import load_json, save_json


def iter_profiles(base_path: str) -> Iterable[tuple[str, dict]]:
    """Yield ``(plant_id, profile_data)`` from ``base_path`` JSON files."""
    path = Path(base_path)
    if not path.is_dir():
        return
    for file in path.glob("*.json"):
        try:
            data = load_json(str(file))
            plant_id = data.get("plant_id") or file.stem
            yield plant_id, data
        except Exception:
            continue


def append_json_log(log_path: Path, entry: dict) -> None:
    """Append ``entry`` to a JSON list stored at ``log_path``."""
    log_path.parent.mkdir(exist_ok=True)
    log_entries = []
    if log_path.is_file():
        try:
            val = load_json(str(log_path))
            if isinstance(val, list):
                log_entries = val
        except Exception:
            pass
    log_entries.append(entry)
    save_json(str(log_path), log_entries)


def latest_env(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Return the most recent environment readings from ``profile``."""

    data: Mapping[str, Any] = {}
    general = profile.get("general")
    if isinstance(general, Mapping):
        data = general.get("latest_env") or {}
    if not data:
        data = profile.get("latest_env") or {}
    return dict(data) if isinstance(data, Mapping) else {}
