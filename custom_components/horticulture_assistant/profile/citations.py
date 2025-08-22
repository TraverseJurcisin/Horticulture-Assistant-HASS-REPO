from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .schema import Citation


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def manual_note(note: str) -> Citation:
    return Citation(
        source="manual",
        title="User-entered setpoint",
        details={"note": note},
        accessed=utcnow_iso(),
    )


def clone_note(from_profile_id: str, variables: List[str]) -> Citation:
    return Citation(
        source="clone",
        title="Cloned from profile",
        details={"profile_id": from_profile_id, "variables": variables},
        accessed=utcnow_iso(),
    )


def opb_ref(field: str, url: str, extra: Dict[str, Any] | None = None) -> Citation:
    det: Dict[str, Any] = {"field": field}
    if extra:
        det.update(extra)
    return Citation(
        source="openplantbook",
        title="OpenPlantbook reference",
        url=url,
        details=det,
        accessed=utcnow_iso(),
    )


def ai_ref(summary: str, links: List[str]) -> Citation:
    return Citation(
        source="ai",
        title="AI-derived recommendation",
        details={"summary": summary, "links": links},
        accessed=utcnow_iso(),
    )
