from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .events import SyncEvent, VectorClock

META_KEY = "__meta__"
OP_KEY = "__op__"


class ConflictPolicy(str, Enum):
    """Supported conflict resolution strategies."""

    LWW = "lww"
    OR_SET = "or_set"
    MV_REGISTER = "mv"


@dataclass(slots=True)
class FieldMeta:
    """Track the last writer metadata for a field."""

    clock: VectorClock
    ts: datetime

    def dominates(self, other: "FieldMeta") -> bool:
        cmp_result = self.clock.compare(other.clock)
        if cmp_result > 0:
            return True
        if cmp_result < 0:
            return False
        return self.ts >= other.ts

    def to_dict(self) -> dict[str, Any]:
        return {"clock": self.clock.to_dict(), "ts": self.ts.isoformat()}

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "FieldMeta":
        clock = VectorClock.from_dict(payload["clock"])
        ts_raw = str(payload["ts"])
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        return cls(clock=clock, ts=ts)


class ConflictResolver:
    """Apply CRDT-aware patches to entity state dictionaries."""

    def __init__(
        self,
        default_policy: ConflictPolicy = ConflictPolicy.LWW,
        field_policies: Mapping[str, ConflictPolicy] | None = None,
    ) -> None:
        self.default_policy = default_policy
        self.field_policies = dict(field_policies or {})

    def apply(self, state: dict[str, Any] | None, event: SyncEvent) -> dict[str, Any]:
        if event.op == "delete":
            return {}

        if state is None:
            state = {}
        state = self._ensure_copy(state)
        meta = state.setdefault(META_KEY, {})
        patch = event.patch or {}
        incoming_meta = FieldMeta(clock=event.vector or VectorClock(event.device_id, 0), ts=event.ts)
        self._apply_patch(state, patch, incoming_meta, (), meta)
        return state

    def _apply_patch(
        self,
        root: dict[str, Any],
        patch: Mapping[str, Any],
        field_meta: FieldMeta,
        path: tuple[str, ...],
        meta_store: dict[str, Any],
    ) -> None:
        for key, value in patch.items():
            current_path = path + (key,)
            path_key = ".".join(current_path)

            if isinstance(value, Mapping) and OP_KEY not in value:
                target = root.get(key)
                if not isinstance(target, dict):
                    target = {}
                root[key] = target
                self._apply_patch(target, value, field_meta, current_path, meta_store)
                continue

            policy = self.field_policies.get(path_key, self.default_policy)
            existing_meta_payload = meta_store.get(path_key)
            existing_meta = None
            if isinstance(existing_meta_payload, Mapping):
                try:
                    existing_meta = FieldMeta.from_dict(existing_meta_payload)
                except Exception:  # pragma: no cover - tolerate corrupted metadata
                    existing_meta = None

            if policy == ConflictPolicy.OR_SET:
                resolved = self._apply_or_set(root.get(key), value)
                root[key] = sorted(resolved)
                meta_store[path_key] = field_meta.to_dict()
                continue

            if policy == ConflictPolicy.MV_REGISTER:
                root[key] = self._apply_mv_register(root.get(key), value)
                meta_store[path_key] = field_meta.to_dict()
                continue

            if existing_meta and not field_meta.dominates(existing_meta):
                continue

            root[key] = value
            meta_store[path_key] = field_meta.to_dict()

    def _apply_or_set(self, current: Any, value: Any) -> set[Any]:
        result: set[Any]
        if isinstance(current, Iterable) and not isinstance(current, (str, bytes, dict)):
            result = set(current)
        else:
            result = set()
        if isinstance(value, Mapping):
            adds = value.get("add", [])
            removes = value.get("remove", [])
        else:
            adds = value or []
            removes = []
        for item in adds:
            result.add(item)
        for item in removes:
            result.discard(item)
        return result

    def _apply_mv_register(self, current: Any, value: Any) -> list[Any]:
        seen: list[Any] = []
        if isinstance(current, Iterable) and not isinstance(current, (str, bytes, dict)):
            for item in current:
                if item not in seen:
                    seen.append(item)
        if isinstance(value, Mapping):
            new_values = value.get("values", [])
        else:
            new_values = value or []
        for item in new_values:
            if item not in seen:
                seen.append(item)
        return seen

    def _ensure_copy(self, state: dict[str, Any]) -> dict[str, Any]:
        copy = {key: value for key, value in state.items() if key != META_KEY}
        if META_KEY in state:
            copy[META_KEY] = dict(state[META_KEY])
        return copy

