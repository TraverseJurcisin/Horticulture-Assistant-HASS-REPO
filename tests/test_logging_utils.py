import logging

import pytest

from custom_components.horticulture_assistant.utils.logging import (
    _LAST,
    _MAX_CODES,
    warn_once,
)


@pytest.mark.asyncio
async def test_warn_once_limits_logs(monkeypatch, caplog):
    logger = logging.getLogger("test")
    now = 1000.0
    monkeypatch.setattr("time.monotonic", lambda: now)
    _LAST.clear()

    with caplog.at_level(logging.WARNING):
        warn_once(logger, "CODE", "first", window=60)
        warn_once(logger, "CODE", "second", window=60)
    assert [r.message for r in caplog.records] == ["CODE: first"]

    caplog.clear()
    now += 61.0
    monkeypatch.setattr("time.monotonic", lambda: now)
    with caplog.at_level(logging.WARNING):
        warn_once(logger, "CODE", "third", window=60)
    assert [r.message for r in caplog.records] == ["CODE: third"]


@pytest.mark.asyncio
async def test_warn_once_different_codes(monkeypatch, caplog):
    """Different codes should log separately within the window."""
    logger = logging.getLogger("test")
    monkeypatch.setattr("time.monotonic", lambda: 0.0)
    _LAST.clear()
    with caplog.at_level(logging.WARNING):
        warn_once(logger, "A", "one", window=60)
        warn_once(logger, "B", "two", window=60)
    assert [r.message for r in caplog.records] == ["A: one", "B: two"]


@pytest.mark.asyncio
async def test_warn_once_prunes_cache(monkeypatch):
    """Cache size should not exceed the configured maximum."""
    logger = logging.getLogger("test_prune")
    logger.propagate = False
    t = [0.0]

    def fake_monotonic():
        return t[0]

    monkeypatch.setattr("time.monotonic", fake_monotonic)
    _LAST.clear()

    for i in range(_MAX_CODES):
        t[0] = float(i)
        warn_once(logger, f"C{i}", "x", window=60)

    assert len(_LAST) == _MAX_CODES
    t[0] = float(_MAX_CODES + 1)
    warn_once(logger, "NEW", "x", window=60)

    assert len(_LAST) == _MAX_CODES
    assert "C0" not in _LAST
