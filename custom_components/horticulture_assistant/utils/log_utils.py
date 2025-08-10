from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Dict

_LAST: Dict[str, datetime] = {}
_WINDOW = timedelta(seconds=60)


def log_limited(logger: logging.Logger, level: int, code: str, msg: str, *args) -> None:
    """Log a message for ``code`` no more than once per window."""
    now = datetime.utcnow()
    last = _LAST.get(code)
    if not last or now - last > _WINDOW:
        logger.log(level, msg, *args)
        _LAST[code] = now
