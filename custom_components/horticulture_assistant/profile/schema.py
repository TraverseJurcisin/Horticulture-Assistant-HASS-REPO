from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

SourceType = str  # manual|clone|openplantbook|ai


@dataclass
class Citation:
    source: SourceType
    title: str
    url: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    accessed: Optional[str] = None


@dataclass
class VariableValue:
    value: Any
    source: SourceType
    citations: List[Citation] = field(default_factory=list)


@dataclass
class PlantProfile:
    plant_id: str
    display_name: str
    species: Optional[str] = None
    variables: Dict[str, VariableValue] = field(default_factory=dict)
    general: Dict[str, Any] = field(default_factory=dict)
    citations: List[Citation] = field(default_factory=list)

    def to_json(self) -> Dict[str, Any]:
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
        }

    @staticmethod
    def from_json(data: Dict[str, Any]) -> "PlantProfile":
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
        )
