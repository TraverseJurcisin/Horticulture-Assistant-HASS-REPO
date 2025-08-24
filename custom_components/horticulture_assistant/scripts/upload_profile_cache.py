#!/usr/bin/env python3
"""Upload cached plant profiles to a remote server."""

from __future__ import annotations

import argparse
import sys
import urllib.request as urlreq
from pathlib import Path

from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()
DEFAULT_CACHE_DIR = ROOT / "data" / "profile_cache"

__all__ = ["list_cached_profiles", "upload_cached_profiles", "main"]


def list_cached_profiles(dir_path: Path = DEFAULT_CACHE_DIR) -> list[Path]:
    """Return sorted list of cached profile JSON files."""
    if not dir_path.exists():
        return []
    return sorted(dir_path.glob("*.json"))


def upload_cached_profiles(
    url: str,
    dir_path: Path = DEFAULT_CACHE_DIR,
    delete: bool = False,
) -> None:
    """Upload each cached profile to ``url`` via HTTP POST.

    If ``delete`` is True, remove each file after a successful upload.
    """
    for path in list_cached_profiles(dir_path):
        with open(path, "rb") as f:
            data = f.read()
        req = urlreq.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            urlreq.urlopen(req)
            print(f"Uploaded {path.name}")
            if delete:
                try:
                    path.unlink()
                except Exception as exc:  # pragma: no cover - fs errors
                    print(f"Failed deleting {path.name}: {exc}", file=sys.stderr)
        except Exception as exc:  # pragma: no cover - network errors
            print(f"Failed uploading {path.name}: {exc}", file=sys.stderr)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Upload cached plant profiles")
    parser.add_argument("url", help="API endpoint accepting profile JSON")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument(
        "--delete",
        action="store_true",
        help="Delete cached profiles after successful upload",
    )
    args = parser.parse_args(argv)

    upload_cached_profiles(args.url, args.cache_dir, delete=args.delete)


if __name__ == "__main__":  # pragma: no cover - manual use
    main()
