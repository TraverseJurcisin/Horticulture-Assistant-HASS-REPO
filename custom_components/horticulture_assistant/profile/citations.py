from __future__ import annotations

from datetime import UTC, datetime

from .schema import Citation

UTC = UTC


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def manual_note(note: str) -> Citation:
    return Citation(
        source="manual",
        title="Manual entry",
        details={"note": note},
        accessed=utcnow_iso(),
    )


def clone_ref(from_profile_id: str, variable: str) -> Citation:
    return Citation(
        source="clone",
        title="Cloned from profile",
        details={"profile_id": from_profile_id, "variable": variable},
        accessed=utcnow_iso(),
    )


def opb_ref(species: str, field: str, url: str) -> Citation:
    return Citation(
        source="openplantbook",
        title="OpenPlantbook",
        url=url,
        details={"species": species, "field": field},
        accessed=utcnow_iso(),
    )


def ai_ref(summary: str, links: list[str]) -> Citation:
    return Citation(
        source="ai",
        title="AI synthesis",
        details={"summary": summary, "links": links},
        accessed=utcnow_iso(),
    )
