"""Tests for the history exporter utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.horticulture_assistant.history.exporter import HistoryExporter


@pytest.mark.asyncio
async def test_cultivation_events_update_index(tmp_path: Path, hass) -> None:
    """Cultivation events should record their ``occurred_at`` timestamp."""

    exporter = HistoryExporter(hass, base_path=tmp_path)

    payload = {
        "event_id": "evt-1",
        "profile_id": "plant-1",
        "occurred_at": "2024-03-02T11:05:00+00:00",
        "event_type": "transplant",
    }

    await exporter.async_append("plant-1", "cultivation", payload)

    index = await exporter.async_index()
    record = index["plant-1"]

    assert record.counts["cultivation"] == 1
    assert record.last_updated == payload["occurred_at"]

    # Ensure the timestamp was written to disk as well for persistence.
    index_file = tmp_path / "index.json"
    written = json.loads(index_file.read_text(encoding="utf-8"))
    assert written["plant-1"]["last_updated"] == payload["occurred_at"]


@pytest.mark.asyncio
async def test_run_events_fall_back_to_ended_timestamp(tmp_path: Path, hass) -> None:
    """Run events without ``started_at`` should use ``ended_at`` timestamps."""

    exporter = HistoryExporter(hass, base_path=tmp_path)

    payload = {
        "run_id": "run-1",
        "profile_id": "plant-1",
        "ended_at": "2024-03-03T09:15:00+00:00",
    }

    await exporter.async_append("plant-1", "run", payload)

    index = await exporter.async_index()
    record = index["plant-1"]

    assert record.counts["run"] == 1
    assert record.last_updated == payload["ended_at"]

    index_file = tmp_path / "index.json"
    written = json.loads(index_file.read_text(encoding="utf-8"))
    assert written["plant-1"]["last_updated"] == payload["ended_at"]
