from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import slugify

from .const import CONF_PROFILE_SCOPE

LOCAL_RELATIVE_PATH = "custom_components/horticulture_assistant/data/local"
PROFILES_DIRNAME = "profiles"


@dataclass
class StoredProfile:
    name: str
    sensors: dict[str, str]
    thresholds: dict[str, Any]
    template: str | None = None
    scope: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


class ProfileStore:
    """Minimal local JSON-backed profile store.

    This helper keeps profile documents under the Home Assistant config path so
    power users can source-control profiles or copy them between installs.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._base = Path(hass.config.path(LOCAL_RELATIVE_PATH)) / PROFILES_DIRNAME
        self._lock = asyncio.Lock()

    async def async_init(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    async def async_list(self) -> list[str]:
        return sorted(path.stem for path in self._base.glob("*.json"))

    async def async_list_profiles(self) -> list[str]:
        return await self.async_list()

    async def async_get(self, name: str) -> dict[str, Any] | None:
        path = self._path_for(name)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    async def async_save(self, profile: StoredProfile) -> None:
        await self._atomic_write(self._path_for(profile.name), profile.to_json())

    async def async_create_profile(
        self,
        name: str,
        sensors: dict[str, str] | None = None,
        clone_from: dict[str, Any] | None = None,
        scope: str | None = None,
    ) -> None:
        clone_payload: dict[str, Any] | None
        if isinstance(clone_from, str) and clone_from:
            clone_payload = await self.async_get(clone_from)
        elif isinstance(clone_from, dict):
            clone_payload = clone_from
        else:
            clone_payload = None

        resolved_scope = scope
        if clone_payload:
            resolved_scope = resolved_scope or clone_payload.get(CONF_PROFILE_SCOPE)
            resolved_scope = resolved_scope or clone_payload.get("scope")

        if sensors is not None:
            sensors_data = dict(sensors)
        elif clone_payload:
            source_sensors = clone_payload.get("sensors")
            sensors_data = dict(source_sensors) if isinstance(source_sensors, dict) else {}
        else:
            sensors_data = {}

        thresholds = deepcopy(clone_payload.get("thresholds", {})) if clone_payload else {}

        data = StoredProfile(
            name=name,
            sensors=sensors_data,
            thresholds=thresholds,
            template=clone_payload.get("template") if clone_payload else None,
            scope=resolved_scope,
        )
        await self.async_save(data)

    async def _atomic_write(self, path: Path, payload: dict[str, Any]) -> None:
        tmp = path.with_suffix(".tmp")
        txt = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        async with self._lock:
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(txt, encoding="utf-8")
            tmp.replace(path)

    def _path_for(self, name: str) -> Path:
        slug = slugify(name) or "profile"
        return self._base / f"{slug}.json"
