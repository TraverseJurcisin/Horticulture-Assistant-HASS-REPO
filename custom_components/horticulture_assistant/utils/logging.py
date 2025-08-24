from __future__ import annotations

import time

_LAST: dict[str, float] = {}
_MAX_CODES = 1024


def warn_once(logger, code: str, message: str, window: int = 60) -> None:
    """Log a warning once per time window for a given code.

    To avoid unbounded growth when many unique codes are used, the cache is
    capped and oldest entries are discarded.
    """
    now = time.monotonic()
    last = _LAST.get(code)
    if last is None or now - last > window:
        if len(_LAST) >= _MAX_CODES:
            oldest = min(_LAST, key=_LAST.get)
            _LAST.pop(oldest, None)
        _LAST[code] = now
        logger.warning("%s: %s", code, message)
