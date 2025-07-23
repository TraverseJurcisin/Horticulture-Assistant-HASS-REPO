"""Utility helpers for generating daily reports."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

__all__ = ["load_recent_entries"]


def load_recent_entries(log_path: Path, hours: float = 24.0) -> List[Dict]:
    """Return log entries from ``log_path`` within the last ``hours``."""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except Exception:
        return []

    cutoff = datetime.utcnow() - timedelta(hours=hours)
    recent: List[Dict] = []
    for entry in data:
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            if datetime.fromisoformat(ts) >= cutoff:
                recent.append(entry)
        except Exception:
            continue
    return recent
