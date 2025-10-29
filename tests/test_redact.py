from __future__ import annotations

from homeassistant.components.diagnostics import REDACTED

from custom_components.horticulture_assistant.utils.redact import redact


def test_redact_handles_iterable_keys_generator() -> None:
    """Generators provided for keys should redact matching entries."""

    payload = {"token": "abc123", "name": "Fern"}
    keys = (key for key in ["token"])

    redacted = redact(payload, keys)

    assert redacted["token"] == REDACTED
    assert redacted["name"] == "Fern"


def test_redact_with_sequence_keeps_unmatched_keys() -> None:
    """Non-sensitive keys remain unchanged after redaction."""

    payload = {"token": "abc123", "name": "Fern"}

    redacted = redact(payload, ["token"])

    assert redacted["token"] == REDACTED
    assert redacted["name"] == "Fern"
