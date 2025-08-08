from __future__ import annotations

"""Helper utilities for command line scripts."""

from pathlib import Path
import sys


def ensure_repo_root_on_path() -> Path:
    """Add the repository root to ``sys.path`` without overriding package order."""
    root = Path(__file__).resolve().parents[3]
    path = str(root)
    if path not in sys.path:
        # ``sys.path``[0] is typically the custom component directory added by
        # individual scripts. Insert the repository root *after* this so that
        # bundled copies of packages (e.g. ``plant_engine``) take precedence
        # over any stub modules at the repository root.
        sys.path.insert(1, path)
    return root
