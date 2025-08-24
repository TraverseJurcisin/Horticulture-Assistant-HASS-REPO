from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

SourceType = str  # manual|clone|openplantbook|ai


@dataclass
class Citation:
    source: SourceType
    title: str
    url: str | None = None
    details: dict[str, Any] | None = None
    accessed: str | None = None


@dataclass
class VariableValue:
    value: Any
    source: SourceType
    citations: list[Citation] = field(default_factory=list)


@dataclass
class PlantProfile:
    plant_id: str
    display_name: str
    species: str | None = None
    variables: dict[str, VariableValue] = field(default_factory=dict)
    general: dict[str, Any] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    last_resolved: str | None = None

    def to_json(self) -> dict[str, Any]:
        def ser(val):
            if isinstance(val, Citation):
                return asdict(val)
            if isinstance(val, VariableValue):
                return {
                    "value": val.value,
                    "source": val.source,
                    "citations": [asdict(c) for c in val.citations],
                }
            return val

        return {
            "plant_id": self.plant_id,
            "display_name": self.display_name,
            "species": self.species,
            "variables": {k: ser(v) for k, v in self.variables.items()},
            "general": self.general,
            "citations": [asdict(c) for c in self.citations],
            "last_resolved": self.last_resolved,
        }

    @staticmethod
    def from_json(data: dict[str, Any]) -> PlantProfile:
        """Create a PlantProfile from a dictionary."""

        variables = {
            key: VariableValue(
                value=value.get("value"),
                source=value.get("source"),
                citations=[Citation(**c) for c in value.get("citations", [])],
            )
            for key, value in (data.get("variables") or {}).items()
        }
        citations = [Citation(**c) for c in data.get("citations", [])]
        return PlantProfile(
            plant_id=data["plant_id"],
            display_name=data["display_name"],
            species=data.get("species"),
            variables=variables,
            general=data.get("general") or {},
            citations=citations,
            last_resolved=data.get("last_resolved"),
        )
