"""Utilities for exporting lifecycle history to disk."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant


def _coerce_timestamp(value: Any) -> str | None:
    """Return a normalised timestamp string or ``None`` for missing values."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _first_timestamp(payload: Mapping[str, Any], *keys: str) -> str | None:
    """Return the first truthy timestamp in ``payload`` for the given ``keys``."""

    for key in keys:
        candidate = _coerce_timestamp(payload.get(key))
        if candidate:
            return candidate
    return None


@dataclass
class HistoryIndex:
    """Simple manifest describing exported history files."""

    profile_id: str
    last_updated: str | None = None
    counts: dict[str, int] = field(default_factory=dict)

    def touch(self, event_type: str, timestamp: str | None) -> None:
        """Update counters and timestamps for ``event_type``."""

        self.counts[event_type] = self.counts.get(event_type, 0) + 1
        if timestamp:
            # store ISO timestamps only, but gracefully skip invalid strings
            try:
                parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                parsed = None
            if parsed is not None:
                self.last_updated = parsed.isoformat()

    def to_json(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "last_updated": self.last_updated,
            "counts": dict(self.counts),
        }


class HistoryExporter:
    """Persist profile history to jsonl files for long term analytics."""

    _EVENT_FILE_MAP = {
        "run": "run_events.jsonl",
        "harvest": "harvest_events.jsonl",
        "nutrient": "nutrient_events.jsonl",
        "cultivation": "cultivation_events.jsonl",
    }

    def __init__(self, hass: HomeAssistant, base_path: Path | None = None) -> None:
        self._hass = hass
        config_dir = Path(hass.config.path("custom_components", "horticulture_assistant", "data", "local"))
        self._base = base_path or (config_dir / "history")
        self._base.mkdir(parents=True, exist_ok=True)
        self._index_path = self._base / "index.json"

    async def async_append(self, profile_id: str, event_type: str, payload: Mapping[str, Any]) -> None:
        """Append ``payload`` to the history log for ``profile_id``."""

        if event_type not in self._EVENT_FILE_MAP:
            raise ValueError(f"unknown history event type {event_type}")
        await self._hass.async_add_executor_job(self._write_entry, profile_id, event_type, dict(payload))

    async def async_index(self) -> dict[str, HistoryIndex]:
        """Return a snapshot of the on-disk index."""

        return await self._hass.async_add_executor_job(self._load_index)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _write_entry(self, profile_id: str, event_type: str, payload: Mapping[str, Any]) -> None:
        file_name = self._EVENT_FILE_MAP[event_type]
        profile_dir = self._base / profile_id
        profile_dir.mkdir(parents=True, exist_ok=True)
        file_path = profile_dir / file_name
        json_line = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        with file_path.open("a", encoding="utf-8") as handle:
            handle.write(json_line)
            handle.write(os.linesep)
        self._update_index(profile_id, event_type, payload)

    def _update_index(self, profile_id: str, event_type: str, payload: Mapping[str, Any]) -> None:
        existing = self._load_index()
        record = existing.get(profile_id) or HistoryIndex(profile_id)
        timestamp = self._extract_timestamp(event_type, payload)
        record.touch(event_type, timestamp)
        existing[profile_id] = record
        serialised = {key: value.to_json() for key, value in existing.items()}
        tmp_path = self._index_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(serialised, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(self._index_path)

    def _load_index(self) -> dict[str, HistoryIndex]:
        if not self._index_path.exists():
            return {}
        try:
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        index: dict[str, HistoryIndex] = {}
        for key, value in data.items():
            counts = value.get("counts") if isinstance(value, Mapping) else {}
            record = HistoryIndex(
                profile_id=key,
                last_updated=value.get("last_updated") if isinstance(value, Mapping) else None,
                counts=dict(counts) if isinstance(counts, Mapping) else {},
            )
            index[key] = record
        return index

    @staticmethod
    def _extract_timestamp(event_type: str, payload: Mapping[str, Any]) -> str | None:
        if not payload:
            return None

        if event_type == "run":
            return _first_timestamp(
                payload,
                "started_at",
                "ended_at",
                "completed_at",
                "start",
                "timestamp",
            )

        if event_type == "harvest":
            return _first_timestamp(payload, "harvested_at", "timestamp")

        if event_type == "nutrient":
            return _first_timestamp(payload, "applied_at", "recorded_at", "timestamp")

        if event_type == "cultivation":
            # ``occurred_at`` is the canonical timestamp on cultivation events but
            # older payloads may still use ``recorded_at`` or ``timestamp``.
            return _first_timestamp(payload, "occurred_at", "recorded_at", "timestamp")

        return None
