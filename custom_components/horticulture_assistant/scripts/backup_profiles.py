#!/usr/bin/env python3
"""Backup or restore plant profiles and registry."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
import zipfile

import sys

# Ensure project root is on the Python path when executed directly
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()
PLANTS_DIR = ROOT / "plants"
REGISTRY_PATH = ROOT / "data/local/plants/plant_registry.json"
DEFAULT_BACKUP_DIR = ROOT / "backups"


def configure_root(path: Path) -> Path:
    """Set global directories relative to ``path`` and return the resolved root."""

    global ROOT, PLANTS_DIR, REGISTRY_PATH, DEFAULT_BACKUP_DIR
    ROOT = path.resolve()
    PLANTS_DIR = ROOT / "plants"
    REGISTRY_PATH = ROOT / "data/local/plants/plant_registry.json"
    DEFAULT_BACKUP_DIR = ROOT / "backups"
    return ROOT

__all__ = [
    "create_backup",
    "restore_backup",
    "list_backups",
    "verify_backup",
    "configure_root",
]


def list_backups(dir_path: Path = DEFAULT_BACKUP_DIR) -> list[Path]:
    """Return sorted list of existing backup archives."""

    if not dir_path.exists():
        return []
    return sorted(dir_path.glob("*_profiles.zip"))


def verify_backup(archive: Path) -> bool:
    """Check ``archive`` for corruption. Returns ``True`` if valid."""

    if not archive.exists():
        return False
    with zipfile.ZipFile(archive, "r") as zf:
        return zf.testzip() is None


def create_backup(output_dir: Path = DEFAULT_BACKUP_DIR, retain: int | None = None) -> Path:
    """Create a ZIP backup of profiles and optionally trim old backups."""

    output_dir.mkdir(parents=True, exist_ok=True)
    # Include microseconds so rapid successive calls don't overwrite archives
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    archive = output_dir / f"{ts}_profiles.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for pf in PLANTS_DIR.glob("*.json"):
            zf.write(pf, arcname=f"plants/{pf.name}")
        if REGISTRY_PATH.exists():
            zf.write(REGISTRY_PATH, arcname="data/local/plants/plant_registry.json")

    if not verify_backup(archive):
        archive.unlink(missing_ok=True)
        raise RuntimeError(f"Backup verification failed for {archive}")

    if retain is not None:
        existing = list_backups(output_dir)
        to_remove = existing if retain <= 0 else existing[:-retain]
        for old in to_remove:
            old.unlink(missing_ok=True)

    return archive


def restore_backup(archive: Path, output_dir: Path = ROOT) -> None:
    """Restore ``archive`` into ``output_dir``."""

    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(output_dir)


def main(argv: list[str] | None = None) -> None:
    root_parser = argparse.ArgumentParser(add_help=False)
    root_parser.add_argument("--root", type=Path, default=ROOT, help="plant data root directory")

    # Parse --root first to determine the correct defaults for other options
    root_args, remaining = root_parser.parse_known_args(argv)
    configure_root(root_args.root)

    parser = argparse.ArgumentParser(description="Backup or restore plant profiles", parents=[root_parser])
    parser.add_argument("--restore", metavar="ZIP", help="Restore from backup zip")
    parser.add_argument("--output", type=Path, default=DEFAULT_BACKUP_DIR, help="directory for backups")
    parser.add_argument("--retain", type=int, help="keep only N recent backups")
    parser.add_argument("--list", action="store_true", help="list existing backups")
    parser.add_argument("--verify", metavar="ZIP", help="verify backup archive")
    args = parser.parse_args(remaining)

    if args.list:
        for arc in list_backups(args.output):
            print(arc)
        return

    if args.verify:
        arc = Path(args.verify)
        if not arc.is_absolute() and arc.parent == Path('.'):
            arc = args.output / arc
        ok = verify_backup(arc)
        msg = "valid" if ok else "CORRUPT"
        print(f"{arc} is {msg}")
        return

    if args.restore:
        arc = Path(args.restore)
        if not arc.is_absolute() and arc.parent == Path('.'):
            arc = args.output / arc
        restore_backup(arc)
        print(f"Restored profiles from {arc}")
        return

    arc = create_backup(args.output, retain=args.retain)
    print(f"Created backup {arc}")
    if not verify_backup(arc):
        print("Warning: backup verification failed", file=sys.stderr)


if __name__ == "__main__":
    main()
