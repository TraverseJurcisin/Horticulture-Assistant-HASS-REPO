#!/usr/bin/env python3
"""Sort the integration manifest for Home Assistant."""

import json
from pathlib import Path


def main() -> None:
    """Load, sort, and rewrite the manifest file."""
    repo_root = Path(__file__).resolve().parents[1]
    mf = repo_root / "custom_components" / "horticulture_assistant" / "manifest.json"
    data = json.loads(mf.read_text(encoding="utf-8"))

    # Pull out required lead keys
    ordered: dict[str, object] = {}
    for key in ("domain", "name"):
        if key in data:
            ordered[key] = data.pop(key)

    # Append the rest in sorted order
    for key in sorted(data):
        ordered[key] = data[key]

    mf.write_text(
        json.dumps(ordered, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("Sorted manifest.json")


if __name__ == "__main__":
    main()
