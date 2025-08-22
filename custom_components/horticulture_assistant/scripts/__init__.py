"""Helper utilities for command line scripts."""

import sys
from pathlib import Path


def ensure_repo_root_on_path() -> Path:
    """Add the repository root to ``sys.path`` without overriding package order."""
    root = Path(__file__).resolve().parents[3]
    path = str(root)
    if path not in sys.path:
        # ``sys.path``[0] is typically the custom component directory added by
        # individual scripts. Insert the repository root *after* this so
        # bundled copies of packages ship with the integration take
        # precedence when resolving imports.
        sys.path.insert(1, path)
    return root
