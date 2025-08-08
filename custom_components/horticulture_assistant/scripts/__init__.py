from __future__ import annotations

"""Helper utilities for command line scripts."""

from pathlib import Path
import sys


def ensure_repo_root_on_path() -> Path:
    """Add the repository root to ``sys.path`` and return it."""
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root
