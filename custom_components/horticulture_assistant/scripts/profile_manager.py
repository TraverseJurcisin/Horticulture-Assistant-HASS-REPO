from __future__ import annotations

"""Utility helpers for editing plant profiles from the command line."""

import argparse
import csv
import json
from pathlib import Path

from scripts import ensure_repo_root_on_path

ROOT = ensure_repo_root_on_path()

from custom_components.horticulture_assistant.utils import (
    bio_profile_loader as loader,
)
from custom_components.horticulture_assistant.utils.json_io import load_json

DEFAULT_PLANTS_DIR = ROOT / "plants"
DEFAULT_GLOBAL_DIR = ROOT / "data" / "global_profiles"
DEFAULT_HISTORY_DIR = ROOT / "data" / "local" / "history"


def attach_sensor(
    plant_id: str,
    sensor_type: str,
    entity_ids: list[str],
    base_dir: Path = DEFAULT_PLANTS_DIR,
) -> bool:
    """Attach sensors to a plant profile without overwriting existing ones."""
    return loader.attach_profile_sensors(plant_id, {sensor_type: entity_ids}, base_dir)


def detach_sensor(
    plant_id: str,
    sensor_type: str,
    entity_ids: list[str] | None = None,
    base_dir: Path = DEFAULT_PLANTS_DIR,
) -> bool:
    """Detach sensors from a plant profile."""
    return loader.detach_profile_sensors(plant_id, {sensor_type: entity_ids}, base_dir)


def set_preference(
    plant_id: str, key: str, value: object, base_dir: Path = DEFAULT_PLANTS_DIR
) -> bool:
    """Set a preference on the plant profile."""
    profile = loader.load_profile_by_id(plant_id, base_dir)
    if not profile:
        return False
    container = profile.get("general") if isinstance(profile.get("general"), dict) else profile
    container[key] = value
    if container is not profile:
        profile["general"] = container
    return loader.save_profile_by_id(plant_id, profile, base_dir)


def load_default_profile(
    plant_type: str,
    plant_id: str,
    base_dir: Path = DEFAULT_PLANTS_DIR,
    global_dir: Path = DEFAULT_GLOBAL_DIR,
) -> bool:
    """Create a new profile ``plant_id`` from a global ``plant_type`` template."""
    template_path = Path(global_dir) / f"{plant_type}.json"
    if not template_path.is_file():
        return False
    data = load_json(str(template_path))
    if not isinstance(data, dict):
        return False
    general = data.get("general", {})
    general["plant_id"] = plant_id
    general.setdefault("display_name", plant_id.replace("_", " ").title())
    data["general"] = general
    return loader.save_profile_by_id(plant_id, data, base_dir)


def _load_history_entries(
    plant_id: str,
    log_name: str,
    base_dir: Path = DEFAULT_PLANTS_DIR,
    history_dir: Path | None = None,
) -> list[object]:
    """Return all persisted history entries for ``plant_id`` and ``log_name``."""

    history_base = history_dir or DEFAULT_HISTORY_DIR
    jsonl_path = Path(history_base) / plant_id / f"{log_name}.jsonl"
    if jsonl_path.is_file():
        try:
            raw_lines = jsonl_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            raw_lines = []
        entries: list[object] = []
        for raw in raw_lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                entries.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        if entries:
            return entries

    log_path = Path(base_dir) / plant_id / f"{log_name}.json"
    if not log_path.is_file():
        return []
    try:
        entries = load_json(str(log_path))
    except Exception:
        return []
    return entries if isinstance(entries, list) else []


def show_history(
    plant_id: str,
    log_name: str,
    base_dir: Path = DEFAULT_PLANTS_DIR,
    lines: int = 5,
    history_dir: Path | None = None,
) -> list[object]:
    """Return the last ``lines`` entries from a log file."""

    entries = _load_history_entries(plant_id, log_name, base_dir, history_dir)
    if not entries:
        return []
    if lines <= 0:
        return []
    return entries[-lines:]


def list_profile_sensors(plant_id: str, base_dir: Path = DEFAULT_PLANTS_DIR) -> dict:
    """Return the ``sensor_entities`` mapping for ``plant_id``."""
    profile = loader.load_profile_by_id(plant_id, base_dir)
    if not profile:
        return {}
    container = profile.get("general") if isinstance(profile.get("general"), dict) else profile
    sensors = container.get("sensor_entities")
    return sensors or {}


def list_global_profiles(global_dir: Path = DEFAULT_GLOBAL_DIR) -> list[str]:
    """List available global profile templates."""
    path = Path(global_dir)
    if not path.is_dir():
        return []
    return sorted(p.stem for p in path.iterdir() if p.is_file() and p.suffix == ".json")


def list_log_files(
    plant_id: str,
    base_dir: Path = DEFAULT_PLANTS_DIR,
    history_dir: Path | None = None,
) -> list[str]:
    """Return the available log names for ``plant_id``."""
    names: set[str] = set()
    log_dir = Path(base_dir) / plant_id
    if log_dir.is_dir():
        names.update(p.stem for p in log_dir.glob("*.json"))
    history_home = (history_dir or DEFAULT_HISTORY_DIR) / plant_id
    if history_home.is_dir():
        names.update(p.stem for p in history_home.glob("*.jsonl"))
    return sorted(names)


def export_history(
    plant_id: str,
    log_name: str,
    output: Path,
    *,
    fmt: str = "jsonl",
    limit: int | None = None,
    base_dir: Path = DEFAULT_PLANTS_DIR,
    history_dir: Path | None = None,
) -> Path | None:
    """Export lifecycle history for ``plant_id`` and return the written path."""

    entries = _load_history_entries(plant_id, log_name, base_dir, history_dir)
    if limit is not None and limit > 0:
        entries = entries[-limit:]
    if not entries:
        return None

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    fmt = fmt.lower()
    if fmt == "csv":
        keys: list[str] = sorted({key for entry in entries if isinstance(entry, dict) for key in entry.keys()})
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=keys)
            writer.writeheader()
            for entry in entries:
                row = {}
                if isinstance(entry, dict):
                    for key in keys:
                        value = entry.get(key)
                        if isinstance(value, (dict, list)):
                            row[key] = json.dumps(value, ensure_ascii=False)
                        else:
                            row[key] = value
                writer.writerow(row)
    elif fmt == "json":
        output.write_text(json.dumps(entries, indent=2, ensure_ascii=False), encoding="utf-8")
    elif fmt == "jsonl":
        lines = [json.dumps(entry, ensure_ascii=False, sort_keys=True) for entry in entries]
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"Unsupported export format: {fmt}")

    return output


def show_preferences(plant_id: str, base_dir: Path = DEFAULT_PLANTS_DIR) -> dict:
    """Return general preferences for ``plant_id``."""
    profile = loader.load_profile_by_id(plant_id, base_dir)
    if not profile:
        return {}
    container = profile.get("general") if isinstance(profile.get("general"), dict) else profile
    prefs = {k: v for k, v in container.items() if k != "sensor_entities"}
    return prefs


def show_global_profile(plant_type: str, global_dir: Path = DEFAULT_GLOBAL_DIR) -> dict:
    """Return the template for ``plant_type`` if available."""
    path = Path(global_dir) / f"{plant_type}.json"
    if not path.is_file():
        return {}
    data = load_json(str(path))
    return data if isinstance(data, dict) else {}


def main(argv: list[str] | None = None) -> None:
    root_parser = argparse.ArgumentParser(add_help=False)
    root_parser.add_argument(
        "--plants-dir",
        type=Path,
        default=DEFAULT_PLANTS_DIR,
        help="directory containing plant profiles",
    )
    root_parser.add_argument(
        "--global-dir",
        type=Path,
        default=DEFAULT_GLOBAL_DIR,
        help="directory containing global profile templates",
    )
    root_parser.add_argument(
        "--history-dir",
        type=Path,
        default=DEFAULT_HISTORY_DIR,
        help="directory containing exported lifecycle logs",
    )

    parser = argparse.ArgumentParser(
        description="Manage plant profiles",
        parents=[root_parser],
    )
    sub = parser.add_subparsers(dest="cmd")

    attach = sub.add_parser("attach-sensor", help="attach sensors")
    attach.add_argument("plant_id")
    attach.add_argument("sensor_type")
    attach.add_argument("entity_ids", nargs="+")

    detach = sub.add_parser("detach-sensor", help="detach sensors")
    detach.add_argument("plant_id")
    detach.add_argument("sensor_type")
    detach.add_argument("entity_ids", nargs="*")

    pref = sub.add_parser("set-pref", help="set preference")
    pref.add_argument("plant_id")
    pref.add_argument("key")
    pref.add_argument("value")

    load = sub.add_parser("load-default", help="load default profile")
    load.add_argument("plant_type")
    load.add_argument("plant_id")

    hist = sub.add_parser("show-history", help="show log entries")
    hist.add_argument("plant_id")
    hist.add_argument("log_name")
    hist.add_argument("--lines", type=int, default=5)

    export_cmd = sub.add_parser("export-history", help="export lifecycle history to disk")
    export_cmd.add_argument("plant_id")
    export_cmd.add_argument("log_name")
    export_cmd.add_argument("--output", "-o", type=Path, required=True)
    export_cmd.add_argument("--format", choices=["jsonl", "json", "csv"], default="jsonl")
    export_cmd.add_argument("--limit", type=int, default=None)

    list_sensors_cmd = sub.add_parser("list-sensors", help="list sensors for a plant")
    list_sensors_cmd.add_argument("plant_id")

    sub.add_parser("list-globals", help="list available global profiles")

    show_prefs_cmd = sub.add_parser("show-prefs", help="display profile preferences")
    show_prefs_cmd.add_argument("plant_id")

    list_logs_cmd = sub.add_parser("list-logs", help="list available log files")
    list_logs_cmd.add_argument("plant_id")

    show_global_cmd = sub.add_parser("show-global", help="show a global profile template")
    show_global_cmd.add_argument("plant_type")

    root_args, remaining = root_parser.parse_known_args(argv)

    plants_dir = root_args.plants_dir
    globals_dir = root_args.global_dir
    history_dir = root_args.history_dir

    args = parser.parse_args(remaining)
    if args.cmd == "attach-sensor":
        ok = attach_sensor(
            args.plant_id,
            args.sensor_type,
            args.entity_ids,
            base_dir=plants_dir,
        )
        print("success" if ok else "failed")
    elif args.cmd == "detach-sensor":
        ok = detach_sensor(
            args.plant_id,
            args.sensor_type,
            args.entity_ids or None,
            base_dir=plants_dir,
        )
        print("success" if ok else "failed")
    elif args.cmd == "set-pref":
        val = json.loads(args.value) if isinstance(args.value, str) else args.value
        ok = set_preference(args.plant_id, args.key, val, base_dir=plants_dir)
        print("success" if ok else "failed")
    elif args.cmd == "load-default":
        ok = load_default_profile(
            args.plant_type,
            args.plant_id,
            base_dir=plants_dir,
            global_dir=globals_dir,
        )
        print("success" if ok else "failed")
    elif args.cmd == "show-history":
        entries = show_history(
            args.plant_id,
            args.log_name,
            base_dir=plants_dir,
            lines=args.lines,
            history_dir=history_dir,
        )
        print(json.dumps(entries, indent=2))
    elif args.cmd == "export-history":
        path = export_history(
            args.plant_id,
            args.log_name,
            args.output,
            fmt=args.format,
            limit=args.limit,
            base_dir=plants_dir,
            history_dir=history_dir,
        )
        if path is None:
            print("no entries")
        else:
            print(path)
    elif args.cmd == "show-prefs":
        prefs = show_preferences(args.plant_id, base_dir=plants_dir)
        print(json.dumps(prefs, indent=2))
    elif args.cmd == "list-logs":
        logs = list_log_files(args.plant_id, base_dir=plants_dir, history_dir=history_dir)
        print("\n".join(logs))
    elif args.cmd == "list-sensors":
        sensors = list_profile_sensors(args.plant_id, base_dir=plants_dir)
        print(json.dumps(sensors, indent=2))
    elif args.cmd == "show-global":
        data = show_global_profile(args.plant_type, global_dir=globals_dir)
        print(json.dumps(data, indent=2))
    elif args.cmd == "list-globals":
        profiles = list_global_profiles(globals_dir)
        print("\n".join(profiles))
    else:
        parser.print_help()


if __name__ == "__main__":  # pragma: no cover - manual usage
    main()
