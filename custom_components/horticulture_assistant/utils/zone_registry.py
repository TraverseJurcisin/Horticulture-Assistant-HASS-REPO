from __future__ import annotations

"""Helpers for managing irrigation zone definitions."""

from dataclasses import dataclass, asdict
from functools import lru_cache
from typing import Dict, List, Optional

from .json_io import load_json, save_json
from .path_utils import config_path

ZONE_REGISTRY_FILE = "zones.json"

__all__ = [
    "ZoneConfig",
    "load_zones",
    "get_zone",
    "list_zones",
    "save_zones",
    "add_zone",
    "attach_plants",
    "detach_plants",
    "attach_solenoids",
    "detach_solenoids",
    "remove_zone",
]


@dataclass(slots=True)
class ZoneConfig:
    """Configuration for an irrigation zone."""

    zone_id: str
    solenoids: List[str]
    plant_ids: List[str]

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@lru_cache(maxsize=1)
def _load_registry(path: str) -> Dict[str, ZoneConfig]:
    try:
        raw = load_json(path)
    except FileNotFoundError:
        return {}
    except Exception:  # pragma: no cover - invalid file
        return {}
    registry: Dict[str, ZoneConfig] = {}
    for zid, data in raw.items():
        sol = data.get("solenoids") or []
        plants = data.get("plant_ids") or []
        registry[str(zid)] = ZoneConfig(str(zid), list(sol), list(plants))
    return registry


def load_zones(hass=None) -> Dict[str, ZoneConfig]:
    """Return mapping of zone_id to :class:`ZoneConfig`."""

    path = config_path(hass, ZONE_REGISTRY_FILE)
    return _load_registry(path)


def get_zone(zone_id: str, hass=None) -> Optional[ZoneConfig]:
    """Return zone configuration for ``zone_id`` if available."""

    zones = load_zones(hass)
    return zones.get(str(zone_id))


def list_zones(hass=None) -> List[str]:
    """Return all known zone IDs sorted alphabetically."""

    return sorted(load_zones(hass).keys())


def save_zones(zones: Dict[str, ZoneConfig], hass=None) -> bool:
    """Persist ``zones`` to ``zones.json``."""

    path = config_path(hass, ZONE_REGISTRY_FILE)
    data = {zid: zone.as_dict() for zid, zone in zones.items()}
    try:
        save_json(path, data)
    except Exception:  # pragma: no cover - unexpected write errors
        return False
    _load_registry.cache_clear()
    return True


def add_zone(zone_id: str, solenoids: List[str] | None = None,
             plant_ids: List[str] | None = None, hass=None) -> bool:
    """Add a new irrigation zone and persist it.

    Returns ``False`` if the zone already exists.
    """

    zones = load_zones(hass)
    if str(zone_id) in zones:
        return False
    zones[str(zone_id)] = ZoneConfig(
        str(zone_id), list(solenoids or []), list(plant_ids or [])
    )
    return save_zones(zones, hass)


def attach_plants(zone_id: str, plant_ids: List[str], hass=None) -> bool:
    """Attach ``plant_ids`` to ``zone_id`` and persist the registry."""

    zones = load_zones(hass)
    zone = zones.get(str(zone_id))
    if not zone:
        return False
    for pid in plant_ids:
        if pid not in zone.plant_ids:
            zone.plant_ids.append(pid)
    return save_zones(zones, hass)


def detach_plants(zone_id: str, plant_ids: List[str], hass=None) -> bool:
    """Remove ``plant_ids`` from ``zone_id`` and persist the registry."""

    zones = load_zones(hass)
    zone = zones.get(str(zone_id))
    if not zone:
        return False
    zone.plant_ids = [pid for pid in zone.plant_ids if pid not in plant_ids]
    return save_zones(zones, hass)


def attach_solenoids(zone_id: str, solenoids: List[str], hass=None) -> bool:
    """Attach ``solenoids`` to ``zone_id`` and persist the registry."""

    zones = load_zones(hass)
    zone = zones.get(str(zone_id))
    if not zone:
        return False
    for sid in solenoids:
        if sid not in zone.solenoids:
            zone.solenoids.append(sid)
    return save_zones(zones, hass)


def detach_solenoids(zone_id: str, solenoids: List[str], hass=None) -> bool:
    """Remove ``solenoids`` from ``zone_id`` and persist the registry."""

    zones = load_zones(hass)
    zone = zones.get(str(zone_id))
    if not zone:
        return False
    zone.solenoids = [sid for sid in zone.solenoids if sid not in solenoids]
    return save_zones(zones, hass)


def remove_zone(zone_id: str, hass=None) -> bool:
    """Delete ``zone_id`` from the registry and persist changes."""

    zones = load_zones(hass)
    if str(zone_id) not in zones:
        return False
    zones.pop(str(zone_id))
    return save_zones(zones, hass)

