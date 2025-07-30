from __future__ import annotations

"""Helper utilities for command line scripts."""

from pathlib import Path
import sys


def ensure_repo_root_on_path() -> Path:
    """Add repository root to ``sys.path`` and return the path."""
    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
