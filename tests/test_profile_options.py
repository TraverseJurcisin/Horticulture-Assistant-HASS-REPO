"""Tests for profile options helpers."""

from __future__ import annotations

from custom_components.horticulture_assistant.profile.options import options_profile_to_dataclass


def test_options_profile_to_dataclass_handles_sequence_citations() -> None:
    """Legacy list-based citation payloads should be supported."""

    options = {
        "name": "Test Plant",
        "thresholds": {"temp": 21},
        "sources": {"temp": {"mode": "manual"}},
        "citations": [
            {
                "field": "temp",
                "mode": "manual",
                "source_detail": "Grower notes",
                "ts": "2024-01-01T00:00:00Z",
            }
        ],
    }

    profile = options_profile_to_dataclass("test", options)

    target = profile.resolved_targets["temp"]
    assert target.annotation.source_type == "manual"
    assert target.citations
    assert target.citations[0].title == "Grower notes"
