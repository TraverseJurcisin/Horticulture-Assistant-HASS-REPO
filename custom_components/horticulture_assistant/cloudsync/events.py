from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

try:
    UTC = datetime.UTC  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - Py<3.11 fallback
    UTC = timezone.utc  # noqa: UP017


@dataclass(slots=True)
class VectorClock:
    """Single-device Lamport clock used to compare edge/cloud events."""

    device: str
    counter: int

    def increment(self) -> VectorClock:
        return VectorClock(device=self.device, counter=self.counter + 1)

    def compare(self, other: VectorClock) -> int:
        """Return 1 if self dominates, -1 if other dominates, 0 if concurrent."""

        if self.device == other.device:
            if self.counter > other.counter:
                return 1
            if self.counter < other.counter:
                return -1
            return 0
        # Different devices → concurrent. Merge handled at policy layer.
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {"device": self.device, "counter": self.counter}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> VectorClock:
        return cls(device=payload["device"], counter=int(payload["counter"]))


@dataclass(slots=True)
class SyncEvent:
    """Represents a change event shared between edge and cloud."""

    event_id: str
    tenant_id: str
    device_id: str
    ts: datetime
    entity_type: str
    entity_id: str
    op: str
    patch: dict[str, Any] | None = None
    vector: VectorClock | None = None
    actor: str | None = None
    signature: str | None = None
    hash_prev: str | None = None
    org_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": self.event_id,
            "tenant_id": self.tenant_id,
            "device_id": self.device_id,
            "ts": self.ts.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z"),
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "op": self.op,
        }
        if self.patch is not None:
            payload["patch"] = self.patch
        if self.vector is not None:
            payload["vector"] = self.vector.to_dict()
        if self.actor is not None:
            payload["actor"] = self.actor
        if self.signature is not None:
            payload["signature"] = self.signature
        if self.hash_prev is not None:
            payload["hash_prev"] = self.hash_prev
        if self.org_id is not None:
            payload["org_id"] = self.org_id
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SyncEvent:
        ts_raw = payload.get("ts")
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")) if isinstance(ts_raw, str) else datetime.now(tz=UTC)
        vector = None
        if isinstance(payload.get("vector"), dict):
            vector = VectorClock.from_dict(payload["vector"])
        return cls(
            event_id=payload["event_id"],
            tenant_id=payload["tenant_id"],
            device_id=payload["device_id"],
            ts=ts,
            entity_type=payload["entity_type"],
            entity_id=str(payload["entity_id"]),
            op=payload["op"],
            patch=payload.get("patch"),
            vector=vector,
            actor=payload.get("actor"),
            signature=payload.get("signature"),
            hash_prev=payload.get("hash_prev"),
            org_id=(str(payload.get("org_id")) if payload.get("org_id") else None),
            metadata=payload.get("metadata", {}),
        )

    @classmethod
    def from_json_line(cls, line: str) -> SyncEvent:
        return cls.from_dict(json.loads(line))


def encode_ndjson(events: Iterable[SyncEvent]) -> str:
    return "\n".join(event.to_json_line() for event in events)


def decode_ndjson(payload: str | bytes) -> list[SyncEvent]:
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8")
    lines = [line for line in payload.splitlines() if line.strip()]
    return [SyncEvent.from_json_line(line) for line in lines]
