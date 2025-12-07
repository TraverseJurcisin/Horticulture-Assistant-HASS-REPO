from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

_NUMBER_PATTERN = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")
_FRACTION_PATTERN = re.compile(
    r"(?P<numerator>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*/\s*(?P<denominator>[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, Mapping):
        return {str(key): item for key, item in value.items()}
    return {}


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _string_or_fallback(*candidates: Any, fallback: str) -> str:
    for candidate in candidates:
        text = _optional_string(candidate)
        if text is not None:
            return text
    return fallback


def _parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts.astimezone(UTC)


SourceType = str  # manual|clone|openplantbook|ai|curated|computed


BADGE_LABELS: dict[str, str] = {
    "inherited": "Inherited from parent",
    "override": "Locally overridden",
    "external": "External source",
    "computed": "Computed",
}

BADGE_ICONS: dict[str, str] = {
    "inherited": "mdi:family-tree",
    "override": "mdi:source-branch",
    "external": "mdi:cloud-download",
    "computed": "mdi:calculator-variant",
}

BADGE_COLORS: dict[str, str] = {
    "inherited": "blue",
    "override": "orange",
    "external": "purple",
    "computed": "teal",
}


@dataclass
class Citation:
    source: SourceType
    title: str
    url: str | None = None
    details: dict[str, Any] | None = None
    accessed: str | None = None


@dataclass
class RunEvent:
    """Represents a cultivation run lifecycle event."""

    run_id: str
    profile_id: str
    species_id: str | None
    started_at: str
    ended_at: str | None = None
    environment: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    targets_met: float | None = None
    targets_total: float | None = None
    success_rate: float | None = None
    stress_events: int | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "profile_id": self.profile_id,
            "species_id": self.species_id,
            "started_at": self.started_at,
        }
        if self.ended_at is not None:
            payload["ended_at"] = self.ended_at
        if self.environment:
            payload["environment"] = dict(self.environment)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        if self.targets_met is not None:
            payload["targets_met"] = self.targets_met
        if self.targets_total is not None:
            payload["targets_total"] = self.targets_total
        if self.success_rate is not None:
            payload["success_rate"] = self.success_rate
        if self.stress_events is not None:
            payload["stress_events"] = self.stress_events
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> RunEvent:
        def _float_or_none(value: Any) -> float | None:
            if value is None:
                return None
            if isinstance(value, bool):
                return None
            if isinstance(value, int | float):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
            if isinstance(value, str):
                text = value.strip()
                if not text:
                    return None
                percent = text.endswith("%")
                if percent:
                    text = text[:-1]
                fraction_match = _FRACTION_PATTERN.search(text)
                if fraction_match:
                    numerator_raw = fraction_match.group("numerator")
                    denominator_raw = fraction_match.group("denominator")
                    try:
                        numerator = float(numerator_raw)
                        denominator = float(denominator_raw)
                    except (TypeError, ValueError):
                        numerator = denominator = None
                    if denominator:
                        ratio = numerator / denominator
                        return ratio / 100 if percent else ratio
                try:
                    parsed = float(text)
                    return parsed / 100 if percent else parsed
                except ValueError:
                    match = _NUMBER_PATTERN.search(text)
                    if match:
                        try:
                            parsed = float(match.group(0))
                            return parsed / 100 if percent else parsed
                        except ValueError:
                            return None
                    return None
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        def _int_or_none(value: Any) -> int | None:
            if isinstance(value, bool):
                return None
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        return RunEvent(
            run_id=_string_or_fallback(data.get("run_id"), data.get("id"), fallback="run"),
            profile_id=_string_or_fallback(data.get("profile_id"), data.get("cultivar_id"), fallback=""),
            species_id=_optional_string(data.get("species_id")),
            started_at=_string_or_fallback(
                data.get("started_at"),
                data.get("start"),
                data.get("timestamp"),
                fallback="",
            ),
            ended_at=_optional_string(data.get("ended_at")),
            environment=_as_dict(data.get("environment")),
            metadata=_as_dict(data.get("metadata")),
            targets_met=_float_or_none(data.get("targets_met")),
            targets_total=_float_or_none(data.get("targets_total")),
            success_rate=_float_or_none(data.get("success_rate")),
            stress_events=_int_or_none(data.get("stress_events")),
        )


@dataclass
class CultivationEvent:
    """Represents a user-recorded cultivation milestone."""

    event_id: str
    profile_id: str
    species_id: str | None
    run_id: str | None
    occurred_at: str
    event_type: str
    title: str | None = None
    notes: str | None = None
    metric_value: float | None = None
    metric_unit: str | None = None
    actor: str | None = None
    location: str | None = None
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": self.event_id,
            "profile_id": self.profile_id,
            "species_id": self.species_id,
            "run_id": self.run_id,
            "occurred_at": self.occurred_at,
            "event_type": self.event_type,
        }
        if self.title is not None:
            payload["title"] = self.title
        if self.notes is not None:
            payload["notes"] = self.notes
        if self.metric_value is not None:
            payload["metric_value"] = self.metric_value
        if self.metric_unit is not None:
            payload["metric_unit"] = self.metric_unit
        if self.actor is not None:
            payload["actor"] = self.actor
        if self.location is not None:
            payload["location"] = self.location
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> CultivationEvent:
        def _float_or_none(value: Any) -> float | None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None

        tags: list[str] = []
        raw_tags = data.get("tags")
        if isinstance(raw_tags, list | tuple | set):
            for item in raw_tags:
                if item is None:
                    continue
                text = item.strip() if isinstance(item, str) else str(item).strip()
                if text:
                    tags.append(text)
        elif raw_tags is not None:
            text = raw_tags.strip() if isinstance(raw_tags, str) else str(raw_tags).strip()
            if text:
                tags = [text]

        return CultivationEvent(
            event_id=_string_or_fallback(data.get("event_id"), data.get("id"), fallback="event"),
            profile_id=_string_or_fallback(data.get("profile_id"), fallback=""),
            species_id=_optional_string(data.get("species_id")),
            run_id=_optional_string(data.get("run_id")),
            occurred_at=_string_or_fallback(data.get("occurred_at"), data.get("timestamp"), fallback=""),
            event_type=_string_or_fallback(data.get("event_type"), data.get("type"), fallback="note"),
            title=_optional_string(data.get("title")),
            notes=_optional_string(data.get("notes")),
            metric_value=_float_or_none(data.get("metric_value")),
            metric_unit=_optional_string(data.get("metric_unit")),
            actor=_optional_string(data.get("actor")),
            location=_optional_string(data.get("location")),
            tags=tags,
            metadata=_as_dict(data.get("metadata")),
        )

    def summary(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": self.event_id,
            "occurred_at": self.occurred_at,
            "event_type": self.event_type,
            "title": self.title,
            "notes": self.notes,
        }
        if self.metric_value is not None:
            payload["metric_value"] = self.metric_value
        if self.metric_unit is not None:
            payload["metric_unit"] = self.metric_unit
        if self.actor is not None:
            payload["actor"] = self.actor
        if self.location is not None:
            payload["location"] = self.location
        if self.tags:
            payload["tags"] = list(self.tags)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return {key: value for key, value in payload.items() if value not in (None, "", [])}


@dataclass
class HarvestEvent:
    """Represents a single harvest outcome."""

    harvest_id: str
    profile_id: str
    species_id: str | None
    run_id: str | None
    harvested_at: str
    yield_grams: float
    area_m2: float | None = None
    wet_weight_grams: float | None = None
    dry_weight_grams: float | None = None
    fruit_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "harvest_id": self.harvest_id,
            "profile_id": self.profile_id,
            "species_id": self.species_id,
            "run_id": self.run_id,
            "harvested_at": self.harvested_at,
            "yield_grams": self.yield_grams,
        }
        if self.area_m2 is not None:
            payload["area_m2"] = self.area_m2
        if self.wet_weight_grams is not None:
            payload["wet_weight_grams"] = self.wet_weight_grams
        if self.dry_weight_grams is not None:
            payload["dry_weight_grams"] = self.dry_weight_grams
        if self.fruit_count is not None:
            payload["fruit_count"] = self.fruit_count
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> HarvestEvent:
        def _parse_float(value: Any, *, default: float | None = None) -> float | None:
            if value is None:
                return default
            if isinstance(value, int | float):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return default
            if isinstance(value, str):
                text = value.strip()
                if not text:
                    return default

                def _collapse_spaces(sample: str) -> str:
                    replacements = {
                        ord("\u00a0"): " ",
                        ord("\u202f"): " ",
                        ord("\u2009"): " ",
                        ord("\u2007"): " ",
                        ord("\u2060"): " ",
                    }
                    collapsed = sample.translate(replacements)
                    return re.sub(r"\s+", " ", collapsed)

                def _strip_thousands(segment: str, separator: str) -> str | None:
                    if separator not in segment:
                        return segment
                    parts = segment.split(separator)
                    if any(part == "" for part in parts):
                        return None
                    for index, chunk in enumerate(parts):
                        if not chunk.isdigit():
                            return None
                        if index == 0:
                            if len(chunk) > 3:
                                return None
                        elif len(chunk) != 3:
                            return None
                    return "".join(parts)

                def _parse_simple_thousands(sample: str, separator: str) -> float | None:
                    sign = ""
                    raw = sample
                    if raw and raw[0] in "+-":
                        sign = raw[0]
                        raw = raw[1:].lstrip()
                    if not raw or not any(ch.isdigit() for ch in raw):
                        return None
                    parts = raw.split(separator)
                    if len(parts) <= 1:
                        return None
                    if any(part == "" for part in parts):
                        return None
                    if not all(part.isdigit() for part in parts):
                        return None
                    if not 1 <= len(parts[0]) <= 3:
                        return None
                    if any(len(part) != 3 for part in parts[1:]):
                        return None
                    number = sign + "".join(parts)
                    try:
                        return float(number)
                    except ValueError:
                        return None

                def _parse_localized_number(sample: str) -> float | None:
                    collapsed = _collapse_spaces(sample)
                    token_match = re.search(r"[-+]?\d[\d., ]*\d", collapsed)
                    if not token_match:
                        return None
                    token = token_match.group(0).strip()
                    if not token:
                        return None

                    Candidate = tuple[float, str, int, int, bool]

                    def _candidate(decimal_sep: str) -> Candidate | None:
                        raw = token
                        sign = ""
                        if raw and raw[0] in "+-":
                            sign = raw[0]
                            raw = raw[1:].lstrip()
                        if not raw or not any(ch.isdigit() for ch in raw):
                            return None
                        decimal_count = raw.count(decimal_sep)
                        if decimal_count > 1:
                            return None
                        used_decimal = decimal_count == 1
                        if used_decimal:
                            integer_part, fractional_part = raw.rsplit(decimal_sep, 1)
                        else:
                            integer_part, fractional_part = raw, ""
                        integer_part = integer_part.strip()
                        fractional_part = fractional_part.strip()
                        if not integer_part and not fractional_part:
                            return None
                        if not integer_part:
                            integer_part = "0"
                        thousands_seps: set[str] = set()
                        if decimal_sep == "," and "." in integer_part:
                            thousands_seps.add(".")
                        if decimal_sep == "." and "," in integer_part:
                            thousands_seps.add(",")
                        if " " in integer_part:
                            thousands_seps.add(" ")
                        stripped_integer = integer_part
                        thousands_count = 0
                        for sep in sorted(thousands_seps):
                            occurrences = stripped_integer.count(sep)
                            if occurrences:
                                stripped_integer = _strip_thousands(stripped_integer, sep)
                                if stripped_integer is None:
                                    return None
                                thousands_count += occurrences
                        stripped_integer = stripped_integer.replace(" ", "")
                        if not stripped_integer:
                            stripped_integer = "0"
                        if not stripped_integer.isdigit():
                            return None
                        if any(sep in fractional_part for sep in thousands_seps):
                            return None
                        if " " in fractional_part:
                            return None
                        if fractional_part and not fractional_part.isdigit():
                            return None
                        fraction_len = len(fractional_part)
                        normalized = stripped_integer
                        if fraction_len:
                            normalized = f"{stripped_integer}.{fractional_part}"
                        result_str = sign + normalized
                        try:
                            value = float(result_str)
                        except ValueError:
                            return None
                        return (value, decimal_sep, fraction_len, thousands_count, used_decimal)

                    candidates: list[Candidate] = []
                    for sep in (".", ","):
                        candidate = _candidate(sep)
                        if candidate is not None:
                            candidates.append(candidate)
                    if not candidates:
                        return None
                    values = {candidate[0] for candidate in candidates}
                    if len(values) == 1:
                        return values.pop()

                    def _resolve_ambiguous() -> float | None:
                        if len(candidates) != 2:
                            return None
                        first, second = candidates
                        for prefer, other in ((first, second), (second, first)):
                            frac_len, other_frac_len = prefer[2], other[2]
                            if frac_len in (1, 2) and other_frac_len not in (1, 2):
                                return prefer[0]
                        for prefer, other in ((first, second), (second, first)):
                            frac_len, thousands_count, other_used_decimal = (
                                prefer[2],
                                prefer[3],
                                other[4],
                            )
                            if frac_len == 0 and thousands_count > 0 and not other_used_decimal:
                                return prefer[0]
                        return None

                    resolved = _resolve_ambiguous()
                    if resolved is not None:
                        return resolved

                    collapsed_token = _collapse_spaces(token)
                    if "," in collapsed_token and "." not in collapsed_token:
                        simple = _parse_simple_thousands(collapsed_token, ",")
                        if simple is not None:
                            return simple
                    return None

                parsed = _parse_localized_number(text)
                if parsed is not None:
                    return parsed
                match = _NUMBER_PATTERN.search(text)
                if match:
                    try:
                        return float(match.group(0))
                    except ValueError:
                        return default
                return default
            try:
                return float(value)
            except (TypeError, ValueError):
                return default

        area_value = _parse_float(data.get("area_m2"))
        yield_value = _parse_float(data.get("yield_grams"), default=0.0) or 0.0
        wet_value = _parse_float(data.get("wet_weight_grams"))
        dry_value = _parse_float(data.get("dry_weight_grams"))

        fruit_raw = data.get("fruit_count")
        fruit_value: int | None
        if fruit_raw is None:
            fruit_value = None
        else:
            parsed = _parse_float(fruit_raw)
            try:
                fruit_value = int(parsed) if parsed is not None else None
            except (TypeError, ValueError):
                fruit_value = None
        return HarvestEvent(
            harvest_id=_string_or_fallback(data.get("harvest_id"), data.get("id"), fallback="harvest"),
            profile_id=_string_or_fallback(data.get("profile_id"), data.get("cultivar_id"), fallback=""),
            species_id=_optional_string(data.get("species_id")),
            run_id=_optional_string(data.get("run_id")),
            harvested_at=_string_or_fallback(data.get("harvested_at"), data.get("timestamp"), fallback=""),
            yield_grams=yield_value,
            area_m2=area_value,
            wet_weight_grams=wet_value,
            dry_weight_grams=dry_value,
            fruit_count=fruit_value,
            metadata=_as_dict(data.get("metadata")),
        )

    def yield_density(self) -> float | None:
        if not self.area_m2 or self.area_m2 <= 0:
            return None
        return round(self.yield_grams / self.area_m2, 3)


@dataclass
class NutrientApplication:
    """Represents a nutrient or fertilizer application event."""

    event_id: str
    profile_id: str
    species_id: str | None
    run_id: str | None
    applied_at: str
    product_id: str | None = None
    product_name: str | None = None
    product_category: str | None = None
    source: str | None = None
    solution_volume_liters: float | None = None
    concentration_ppm: float | None = None
    ec_ms: float | None = None
    ph: float | None = None
    additives: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": self.event_id,
            "profile_id": self.profile_id,
            "species_id": self.species_id,
            "run_id": self.run_id,
            "applied_at": self.applied_at,
        }
        if self.product_id is not None:
            payload["product_id"] = self.product_id
        if self.product_name is not None:
            payload["product_name"] = self.product_name
        if self.product_category is not None:
            payload["product_category"] = self.product_category
        if self.source is not None:
            payload["source"] = self.source
        if self.solution_volume_liters is not None:
            payload["solution_volume_liters"] = self.solution_volume_liters
        if self.concentration_ppm is not None:
            payload["concentration_ppm"] = self.concentration_ppm
        if self.ec_ms is not None:
            payload["ec_ms"] = self.ec_ms
        if self.ph is not None:
            payload["ph"] = self.ph
        if self.additives:
            payload["additives"] = list(self.additives)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> NutrientApplication:
        def _float(value: Any) -> float | None:
            try:
                if value is None:
                    return None
                return float(value)
            except (TypeError, ValueError):
                return None

        def _list(value: Any) -> list[str]:
            if isinstance(value, list):
                return [str(item) for item in value]
            if isinstance(value, tuple):
                return [str(item) for item in value]
            if value is None:
                return []
            return [str(value)]

        def _float_pair(primary_key: str, fallback_key: str | None = None) -> float | None:
            primary = _float(data.get(primary_key))
            if primary is not None:
                return primary
            if fallback_key is not None:
                return _float(data.get(fallback_key))
            return None

        return NutrientApplication(
            event_id=_string_or_fallback(data.get("event_id"), data.get("id"), fallback="nutrient"),
            profile_id=_string_or_fallback(data.get("profile_id"), fallback=""),
            species_id=_optional_string(data.get("species_id")),
            run_id=_optional_string(data.get("run_id")),
            applied_at=_string_or_fallback(data.get("applied_at"), data.get("timestamp"), fallback=""),
            product_id=_optional_string(data.get("product_id")),
            product_name=_optional_string(data.get("product_name")),
            product_category=_optional_string(data.get("product_category")),
            source=_optional_string(data.get("source")),
            solution_volume_liters=_float_pair("solution_volume_liters", "volume_liters"),
            concentration_ppm=_float_pair("concentration_ppm", "ppm"),
            ec_ms=_float_pair("ec_ms", "ec"),
            ph=_float(data.get("ph")),
            additives=_list(data.get("additives")),
            metadata=_as_dict(data.get("metadata")),
        )

    def summary(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "event_id": self.event_id,
            "applied_at": self.applied_at,
            "product_id": self.product_id,
            "product_name": self.product_name,
            "run_id": self.run_id,
            "solution_volume_liters": self.solution_volume_liters,
            "concentration_ppm": self.concentration_ppm,
            "ec_ms": self.ec_ms,
            "ph": self.ph,
        }
        if self.additives:
            payload["additives"] = list(self.additives)
        if self.source:
            payload["source"] = self.source
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return {key: value for key, value in payload.items() if value is not None and value != []}


@dataclass
class YieldStatistic:
    """Summarised statistic for a profile or species."""

    stat_id: str
    scope: Literal["species", "cultivar"]
    profile_id: str
    computed_at: str
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "stat_id": self.stat_id,
            "scope": self.scope,
            "profile_id": self.profile_id,
            "computed_at": self.computed_at,
            "metrics": dict(self.metrics),
        }
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> YieldStatistic:
        metrics: dict[str, float] = {}
        metric_payload = data.get("metrics")
        if isinstance(metric_payload, Mapping):
            for key, value in metric_payload.items():
                try:
                    metrics[str(key)] = float(value)
                except (TypeError, ValueError):
                    continue
        return YieldStatistic(
            stat_id=_string_or_fallback(data.get("stat_id"), data.get("id"), fallback="stat"),
            scope=_string_or_fallback(data.get("scope"), fallback="cultivar"),
            profile_id=_string_or_fallback(data.get("profile_id"), fallback=""),
            computed_at=_string_or_fallback(data.get("computed_at"), data.get("timestamp"), fallback=""),
            metrics=metrics,
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass
class FieldAnnotation:
    """Metadata describing how a resolved target value was obtained."""

    source_type: SourceType
    source_ref: list[str] = field(default_factory=list)
    method: str | None = None
    confidence: float | None = None
    staleness_days: float | None = None
    is_stale: bool = False
    overlay: Any | None = None
    overlay_provenance: list[str] = field(default_factory=list)
    overlay_source_type: str | None = None
    overlay_source_ref: list[str] = field(default_factory=list)
    overlay_method: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "source_type": self.source_type,
        }
        if self.source_ref:
            payload["source_ref"] = list(self.source_ref)
        if self.method is not None:
            payload["method"] = self.method
        if self.confidence is not None:
            payload["confidence"] = self.confidence
        if self.staleness_days is not None:
            payload["staleness_days"] = self.staleness_days
        if self.is_stale:
            payload["is_stale"] = self.is_stale
        if self.overlay is not None:
            payload["overlay"] = self.overlay
        if self.overlay_provenance:
            payload["overlay_provenance"] = list(self.overlay_provenance)
        if self.overlay_source_type is not None:
            payload["overlay_source_type"] = self.overlay_source_type
        if self.overlay_source_ref:
            payload["overlay_source_ref"] = list(self.overlay_source_ref)
        if self.overlay_method is not None:
            payload["overlay_method"] = self.overlay_method
        if self.extras:
            payload["extras"] = self.extras
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> FieldAnnotation:
        source_type = data.get("source_type") or data.get("source") or "unknown"
        extras = data.get("extras") or {}
        overlay_provenance = data.get("overlay_provenance") or []
        source_ref_raw = data.get("source_ref") or []
        source_ref = [source_ref_raw] if isinstance(source_ref_raw, str) else [str(item) for item in source_ref_raw]
        return FieldAnnotation(
            source_type=source_type,
            source_ref=source_ref,
            method=data.get("method"),
            confidence=data.get("confidence"),
            staleness_days=data.get("staleness_days"),
            is_stale=bool(data.get("is_stale", False)),
            overlay=data.get("overlay"),
            overlay_provenance=[str(item) for item in overlay_provenance],
            overlay_source_type=data.get("overlay_source_type"),
            overlay_source_ref=[str(item) for item in (data.get("overlay_source_ref") or [])],
            overlay_method=data.get("overlay_method"),
            extras=dict(extras) if isinstance(extras, dict) else {},
        )

    def provenance_payload(
        self,
        *,
        include_overlay: bool = True,
        include_extras: bool = True,
    ) -> dict[str, Any]:
        """Return a serialisable provenance summary for UI/diagnostics."""

        extras = dict(self.extras or {})
        inheritance_depth = extras.get("inheritance_depth")
        inheritance_chain = extras.get("inheritance_chain") or list(self.source_ref)
        provenance_chain = extras.get("provenance") or inheritance_chain
        origin_profile_id = extras.get("source_profile_id")
        if origin_profile_id is None and provenance_chain:
            origin_profile_id = provenance_chain[-1]

        payload: dict[str, Any] = {
            "source_type": self.source_type,
            "source_ref": list(self.source_ref),
            "method": self.method,
            "confidence": self.confidence,
            "staleness_days": self.staleness_days,
            "is_stale": self.is_stale,
            "inheritance_depth": inheritance_depth,
            "inheritance_chain": list(inheritance_chain) if inheritance_chain else None,
            "inheritance_reason": extras.get("inheritance_reason"),
            "provenance_chain": list(provenance_chain) if provenance_chain else None,
            "origin_profile_id": origin_profile_id,
            "origin_profile_type": extras.get("source_profile_type"),
            "origin_profile_name": extras.get("source_profile_name"),
        }

        payload["is_inherited"] = bool(self.source_type == "inheritance" or (inheritance_depth is not None))

        source_type = str(self.source_type or "unknown")
        if payload["is_inherited"]:
            badge_key = "inherited"
        elif source_type in {"manual", "local_override"}:
            badge_key = "override"
        elif source_type == "computed":
            badge_key = "computed"
        else:
            badge_key = "external"

        payload["badge"] = badge_key
        if label := BADGE_LABELS.get(badge_key):
            payload["badge_label"] = label
        if icon := BADGE_ICONS.get(badge_key):
            payload["badge_icon"] = icon
        if colour := BADGE_COLORS.get(badge_key):
            payload["badge_color"] = colour

        if include_overlay:
            if self.overlay is not None:
                payload["overlay"] = self.overlay
            if self.overlay_provenance:
                payload["overlay_provenance"] = list(self.overlay_provenance)
            if self.overlay_source_type is not None:
                payload["overlay_source_type"] = self.overlay_source_type
            if self.overlay_source_ref:
                payload["overlay_source_ref"] = list(self.overlay_source_ref)
            if self.overlay_method is not None:
                payload["overlay_method"] = self.overlay_method

        if include_extras and extras:
            payload["extras"] = extras

        # Remove keys with ``None`` values for a cleaner payload when requested.
        return {key: value for key, value in payload.items() if value is not None}


@dataclass
class ProfileLibrarySection:
    """Canonical profile data sourced from the cloud library."""

    profile_id: str
    profile_type: str = "line"
    tenant_id: str | None = None
    identity: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)
    parents: list[str] = field(default_factory=list)
    policies: dict[str, Any] = field(default_factory=dict)
    stable_knowledge: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
    traits: dict[str, Any] = field(default_factory=dict)
    curated_targets: dict[str, Any] = field(default_factory=dict)
    diffs_vs_parent: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type,
            "identity": self.identity,
            "taxonomy": self.taxonomy,
            "parents": list(self.parents),
            "policies": self.policies,
            "stable_knowledge": self.stable_knowledge,
            "lifecycle": self.lifecycle,
            "traits": self.traits,
            "curated_targets": self.curated_targets,
            "diffs_vs_parent": self.diffs_vs_parent,
            "tags": list(self.tags),
        }
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.metadata:
            payload["metadata"] = self.metadata
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any], *, fallback_id: str) -> ProfileLibrarySection:
        parents_raw = data.get("parents") or []
        parents = [parents_raw] if isinstance(parents_raw, str) else [str(item) for item in parents_raw]
        tags_raw = data.get("tags") or []
        tags = [tags_raw] if isinstance(tags_raw, str) else [str(item) for item in tags_raw]
        return ProfileLibrarySection(
            profile_id=str(data.get("profile_id") or fallback_id),
            profile_type=str(data.get("profile_type", "line")),
            tenant_id=data.get("tenant_id"),
            identity=_as_dict(data.get("identity")),
            taxonomy=_as_dict(data.get("taxonomy")),
            parents=parents,
            policies=_as_dict(data.get("policies")),
            stable_knowledge=_as_dict(data.get("stable_knowledge")),
            lifecycle=_as_dict(data.get("lifecycle")),
            traits=_as_dict(data.get("traits")),
            curated_targets=_as_dict(data.get("curated_targets")),
            diffs_vs_parent=_as_dict(data.get("diffs_vs_parent")),
            tags=tags,
            metadata=_as_dict(data.get("metadata")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class ProfileLocalSection:
    """Locally authoritative profile details stored on the edge."""

    species: str | None = None
    general: dict[str, Any] = field(default_factory=dict)
    local_overrides: dict[str, Any] = field(default_factory=dict)
    resolver_state: dict[str, Any] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    event_history: list[CultivationEvent] = field(default_factory=list)
    run_history: list[RunEvent] = field(default_factory=list)
    harvest_history: list[HarvestEvent] = field(default_factory=list)
    nutrient_history: list[NutrientApplication] = field(default_factory=list)
    statistics: list[YieldStatistic] = field(default_factory=list)
    last_resolved: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "general": self.general,
            "local_overrides": self.local_overrides,
            "resolver_state": self.resolver_state,
            "citations": [asdict(cit) for cit in self.citations],
            "event_history": [event.to_json() for event in self.event_history],
            "run_history": [event.to_json() for event in self.run_history],
            "harvest_history": [event.to_json() for event in self.harvest_history],
            "nutrient_history": [event.to_json() for event in self.nutrient_history],
            "statistics": [stat.to_json() for stat in self.statistics],
        }
        if self.species is not None:
            payload["species"] = self.species
        if self.last_resolved is not None:
            payload["last_resolved"] = self.last_resolved
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileLocalSection:
        citations = [Citation(**item) for item in data.get("citations", []) or [] if isinstance(item, Mapping)]
        event_history: list[CultivationEvent] = []
        for item in data.get("event_history", []) or []:
            if isinstance(item, Mapping):
                event_history.append(CultivationEvent.from_json(item))
        run_history: list[RunEvent] = []
        for item in data.get("run_history", []) or []:
            if isinstance(item, Mapping):
                run_history.append(RunEvent.from_json(item))
        harvest_history: list[HarvestEvent] = []
        for item in data.get("harvest_history", []) or []:
            if isinstance(item, Mapping):
                harvest_history.append(HarvestEvent.from_json(item))
        nutrient_history: list[NutrientApplication] = []
        for item in data.get("nutrient_history", []) or []:
            if isinstance(item, Mapping):
                nutrient_history.append(NutrientApplication.from_json(item))
        statistics: list[YieldStatistic] = []
        for item in data.get("statistics", []) or []:
            if isinstance(item, Mapping):
                statistics.append(YieldStatistic.from_json(item))
        return ProfileLocalSection(
            species=data.get("species"),
            general=_as_dict(data.get("general")),
            local_overrides=_as_dict(data.get("local_overrides") or data.get("overrides")),
            resolver_state=_as_dict(data.get("resolver_state")),
            citations=citations,
            event_history=event_history,
            run_history=run_history,
            harvest_history=harvest_history,
            nutrient_history=nutrient_history,
            statistics=statistics,
            last_resolved=data.get("last_resolved"),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            metadata=_as_dict(data.get("metadata")),
        )


@dataclass
class ResolvedTarget:
    """Resolved target value including provenance annotations."""

    value: Any
    annotation: FieldAnnotation
    citations: list[Citation] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "annotation": self.annotation.to_json(),
            "citations": [asdict(cit) for cit in self.citations],
        }

    def to_legacy(self) -> dict[str, Any]:
        """Return a legacy ``variables`` style payload for compatibility."""

        payload: dict[str, Any] = {
            "value": self.value,
            "source": self.annotation.source_type,
            "annotation": self.annotation.to_json(),
        }
        if self.citations:
            payload["citations"] = [asdict(cit) for cit in self.citations]
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> ResolvedTarget:
        if "annotation" in data and isinstance(data["annotation"], dict):
            annotation = FieldAnnotation.from_json(data["annotation"])
        else:
            annotation = FieldAnnotation(
                source_type=data.get("source") or data.get("source_type") or "unknown",
                source_ref=data.get("source_ref") or [],
                method=data.get("method"),
                confidence=data.get("confidence"),
            )
        citations: list[Citation] = []
        raw_citations = data.get("citations")
        if isinstance(raw_citations, Mapping):
            candidates = raw_citations.values()
        elif isinstance(raw_citations, Sequence) and not isinstance(raw_citations, str | bytes | bytearray):
            candidates = raw_citations
        else:
            candidates = ()
        for citation in candidates:
            if isinstance(citation, Mapping):
                citations.append(Citation(**dict(citation)))
        return ResolvedTarget(value=data.get("value"), annotation=annotation, citations=citations)


@dataclass
class ProfileContribution:
    profile_id: str
    child_id: str
    stats_version: str | None = None
    computed_at: str | None = None
    n_runs: int | None = None
    weight: float | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "child_id": self.child_id,
        }
        if self.stats_version is not None:
            payload["stats_version"] = self.stats_version
        if self.computed_at is not None:
            payload["computed_at"] = self.computed_at
        if self.n_runs is not None:
            payload["n_runs"] = self.n_runs
        if self.weight is not None:
            payload["weight"] = self.weight
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> ProfileContribution:
        return ProfileContribution(
            profile_id=str(data.get("profile_id", "")),
            child_id=str(data.get("child_id", "")),
            stats_version=data.get("stats_version"),
            computed_at=data.get("computed_at"),
            n_runs=data.get("n_runs"),
            weight=data.get("weight"),
        )


@dataclass
class ComputedStatSnapshot:
    stats_version: str | None = None
    computed_at: str | None = None
    snapshot_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    contributions: list[ProfileContribution] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "payload": self.payload,
            "contributions": [contrib.to_json() for contrib in self.contributions],
        }
        if self.stats_version is not None:
            payload["stats_version"] = self.stats_version
        if self.computed_at is not None:
            payload["computed_at"] = self.computed_at
        if self.snapshot_id is not None:
            payload["snapshot_id"] = self.snapshot_id
        return payload

    @staticmethod
    def from_json(data: dict[str, Any]) -> ComputedStatSnapshot:
        contributions = [
            ProfileContribution.from_json(item)
            for item in data.get("contributions", []) or []
            if isinstance(item, dict)
        ]
        payload = data.get("payload") or {}
        return ComputedStatSnapshot(
            stats_version=data.get("stats_version"),
            computed_at=data.get("computed_at"),
            snapshot_id=data.get("snapshot_id"),
            payload=payload if isinstance(payload, dict) else {},
            contributions=contributions,
        )


@dataclass
class ProfileResolvedSection:
    """Runtime resolved data derived from local/cloud/manual sources."""

    thresholds: dict[str, Any] = field(default_factory=dict)
    resolved_targets: dict[str, ResolvedTarget] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    citation_map: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance_map: dict[str, Any] = field(default_factory=dict)
    last_resolved: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "thresholds": dict(self.thresholds),
            "resolved_targets": {key: value.to_json() for key, value in self.resolved_targets.items()},
        }
        if self.variables:
            payload["variables"] = dict(self.variables)
        if self.citation_map:
            payload["citation_map"] = dict(self.citation_map)
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        if self.provenance_map:
            payload["provenance_map"] = dict(self.provenance_map)
        if self.last_resolved is not None:
            payload["last_resolved"] = self.last_resolved
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileResolvedSection:
        thresholds = _as_dict(data.get("thresholds"))
        resolved_targets: dict[str, ResolvedTarget] = {}
        resolved_payload = data.get("resolved_targets") or {}
        if isinstance(resolved_payload, Mapping):
            for key, value in resolved_payload.items():
                if isinstance(value, Mapping):
                    resolved_targets[str(key)] = ResolvedTarget.from_json(dict(value))
        variables = _as_dict(data.get("variables"))
        for key, target in resolved_targets.items():
            variables.setdefault(str(key), target.to_legacy())
        citation_map = _as_dict(data.get("citation_map"))
        metadata = _as_dict(data.get("metadata"))
        provenance_map = _as_dict(data.get("provenance_map"))
        last_resolved = data.get("last_resolved")
        return ProfileResolvedSection(
            thresholds=thresholds,
            resolved_targets=resolved_targets,
            variables=variables,
            citation_map=citation_map,
            metadata=metadata,
            provenance_map=provenance_map,
            last_resolved=last_resolved,
        )


@dataclass
class ProfileComputedSection:
    """Computed statistics cached from the cloud resolver."""

    snapshots: list[ComputedStatSnapshot] = field(default_factory=list)
    latest: ComputedStatSnapshot | None = None
    contributions: list[ProfileContribution] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "snapshots": [snapshot.to_json() for snapshot in self.snapshots],
        }
        if self.latest is not None:
            payload["latest"] = self.latest.to_json()
        if self.contributions:
            payload["contributions"] = [contrib.to_json() for contrib in self.contributions]
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileComputedSection:
        snapshots: list[ComputedStatSnapshot] = []
        snapshot_payloads = data.get("snapshots")
        if isinstance(snapshot_payloads, list):
            for item in snapshot_payloads:
                if isinstance(item, Mapping):
                    snapshots.append(ComputedStatSnapshot.from_json(dict(item)))
        latest_payload = data.get("latest")
        latest = ComputedStatSnapshot.from_json(dict(latest_payload)) if isinstance(latest_payload, Mapping) else None
        contributions_payload = data.get("contributions")
        contributions: list[ProfileContribution] = []
        if isinstance(contributions_payload, list):
            for item in contributions_payload:
                if isinstance(item, Mapping):
                    contributions.append(ProfileContribution.from_json(dict(item)))
        metadata = _as_dict(data.get("metadata"))
        if latest and all(latest is not snap for snap in snapshots):
            snapshots.insert(0, latest)
        return ProfileComputedSection(
            snapshots=snapshots,
            latest=latest or (snapshots[0] if snapshots else None),
            contributions=contributions,
            metadata=metadata,
        )


@dataclass
class ProfileLineageEntry:
    """An entry in the lineage chain used for inheritance."""

    profile_id: str
    profile_type: str = "line"
    depth: int = 0
    role: str = "self"
    tenant_id: str | None = None
    parents: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)
    policies: dict[str, Any] = field(default_factory=dict)
    stable_knowledge: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
    traits: dict[str, Any] = field(default_factory=dict)
    curated_targets: dict[str, Any] = field(default_factory=dict)
    diffs_vs_parent: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "profile_id": self.profile_id,
            "profile_type": self.profile_type,
            "depth": self.depth,
            "role": self.role,
            "parents": list(self.parents),
            "tags": list(self.tags),
            "identity": dict(self.identity),
            "taxonomy": dict(self.taxonomy),
            "policies": dict(self.policies),
            "stable_knowledge": dict(self.stable_knowledge),
            "lifecycle": dict(self.lifecycle),
            "traits": dict(self.traits),
            "curated_targets": dict(self.curated_targets),
            "diffs_vs_parent": dict(self.diffs_vs_parent),
        }
        if self.tenant_id is not None:
            payload["tenant_id"] = self.tenant_id
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        if self.created_at is not None:
            payload["created_at"] = self.created_at
        if self.updated_at is not None:
            payload["updated_at"] = self.updated_at
        return payload

    @staticmethod
    def from_json(data: Mapping[str, Any]) -> ProfileLineageEntry:
        parents_raw = data.get("parents") or []
        parents = [parents_raw] if isinstance(parents_raw, str) else [str(item) for item in parents_raw]
        tags_raw = data.get("tags") or []
        tags = [tags_raw] if isinstance(tags_raw, str) else [str(item) for item in tags_raw]
        return ProfileLineageEntry(
            profile_id=str(data.get("profile_id")),
            profile_type=str(data.get("profile_type", "line")),
            depth=int(data.get("depth", 0)),
            role=str(data.get("role", "self")),
            tenant_id=data.get("tenant_id"),
            parents=parents,
            tags=tags,
            identity=_as_dict(data.get("identity")),
            taxonomy=_as_dict(data.get("taxonomy")),
            policies=_as_dict(data.get("policies")),
            stable_knowledge=_as_dict(data.get("stable_knowledge")),
            lifecycle=_as_dict(data.get("lifecycle")),
            traits=_as_dict(data.get("traits")),
            curated_targets=_as_dict(data.get("curated_targets")),
            diffs_vs_parent=_as_dict(data.get("diffs_vs_parent")),
            metadata=_as_dict(data.get("metadata")),
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
        )


@dataclass
class ProfileSections:
    """Grouped sections that compose the full profile envelope."""

    library: ProfileLibrarySection
    local: ProfileLocalSection
    resolved: ProfileResolvedSection
    computed: ProfileComputedSection

    def to_json(self) -> dict[str, Any]:
        return {
            "library": self.library.to_json(),
            "local": self.local.to_json(),
            "resolved": self.resolved.to_json(),
            "computed": self.computed.to_json(),
        }

    @staticmethod
    def from_json(data: Mapping[str, Any], *, fallback_id: str) -> ProfileSections:
        library_payload = data.get("library")
        if isinstance(library_payload, Mapping):
            library = ProfileLibrarySection.from_json(library_payload, fallback_id=fallback_id)
        else:
            library = ProfileLibrarySection(profile_id=fallback_id)

        local_payload = data.get("local")
        local = (
            ProfileLocalSection.from_json(local_payload)
            if isinstance(local_payload, Mapping)
            else ProfileLocalSection()
        )

        resolved_payload = data.get("resolved")
        resolved = (
            ProfileResolvedSection.from_json(resolved_payload)
            if isinstance(resolved_payload, Mapping)
            else ProfileResolvedSection()
        )

        computed_payload = data.get("computed")
        computed = (
            ProfileComputedSection.from_json(computed_payload)
            if isinstance(computed_payload, Mapping)
            else ProfileComputedSection()
        )

        return ProfileSections(
            library=library,
            local=local,
            resolved=resolved,
            computed=computed,
        )


@dataclass
class BioProfile:
    """Comprehensive offline profile representation used by the add-on."""

    profile_id: str
    display_name: str
    profile_type: str = "line"
    species: str | None = None
    tenant_id: str | None = None
    parents: list[str] = field(default_factory=list)
    identity: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)
    policies: dict[str, Any] = field(default_factory=dict)
    stable_knowledge: dict[str, Any] = field(default_factory=dict)
    lifecycle: dict[str, Any] = field(default_factory=dict)
    traits: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    curated_targets: dict[str, Any] = field(default_factory=dict)
    diffs_vs_parent: dict[str, Any] = field(default_factory=dict)
    library_metadata: dict[str, Any] = field(default_factory=dict)
    library_created_at: str | None = None
    library_updated_at: str | None = None
    local_overrides: dict[str, Any] = field(default_factory=dict)
    resolver_state: dict[str, Any] = field(default_factory=dict)
    resolved_targets: dict[str, ResolvedTarget] = field(default_factory=dict)
    computed_stats: list[ComputedStatSnapshot] = field(default_factory=list)
    general: dict[str, Any] = field(default_factory=dict)
    citations: list[Citation] = field(default_factory=list)
    local_metadata: dict[str, Any] = field(default_factory=dict)
    event_history: list[CultivationEvent] = field(default_factory=list)
    run_history: list[RunEvent] = field(default_factory=list)
    harvest_history: list[HarvestEvent] = field(default_factory=list)
    nutrient_history: list[NutrientApplication] = field(default_factory=list)
    statistics: list[YieldStatistic] = field(default_factory=list)
    last_resolved: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    sections: ProfileSections | None = None
    lineage: list[ProfileLineageEntry] = field(default_factory=list)

    @property
    def plant_id(self) -> str:
        """Backward compatible alias for :attr:`profile_id`."""

        return self.profile_id

    @plant_id.setter
    def plant_id(self, value: str) -> None:
        self.profile_id = value

    @property
    def species_profile_id(self) -> str | None:
        """Return the associated species identifier, if any."""

        return self.species

    @species_profile_id.setter
    def species_profile_id(self, value: str | None) -> None:
        self.species = value

    def resolved_values(self) -> dict[str, Any]:
        """Return the resolved values without metadata."""

        return {key: target.value for key, target in self.resolved_targets.items()}

    def resolved_provenance(
        self,
        *,
        include_overlay: bool = True,
        include_extras: bool = True,
        include_citations: bool = True,
    ) -> dict[str, Any]:
        """Return provenance metadata for each resolved target."""

        provenance: dict[str, Any] = {}
        for key, target in self.resolved_targets.items():
            payload = target.annotation.provenance_payload(
                include_overlay=include_overlay,
                include_extras=include_extras,
            )
            payload["value"] = target.value
            if include_citations and target.citations:
                payload["citations"] = [asdict(cit) for cit in target.citations]
            provenance[str(key)] = payload
        return provenance

    def provenance_summary(self) -> dict[str, Any]:
        """Return a compact provenance summary for UI summaries."""

        summary: dict[str, Any] = {}
        for key, target in self.resolved_targets.items():
            payload = target.annotation.provenance_payload(
                include_overlay=False,
                include_extras=False,
            )
            payload["value"] = target.value
            summary[str(key)] = payload
        return summary

    def provenance_badges(self) -> dict[str, Any]:
        """Return provenance badge metadata for quick UI presentation."""

        badges: dict[str, Any] = {}
        for key, payload in self.provenance_summary().items():
            badge_key = payload.get("badge")
            if not badge_key:
                continue
            badges[key] = {
                "badge": badge_key,
                "label": payload.get("badge_label", BADGE_LABELS.get(badge_key, badge_key.title())),
                "icon": payload.get("badge_icon", BADGE_ICONS.get(badge_key)),
                "color": payload.get("badge_color", BADGE_COLORS.get(badge_key)),
                "is_inherited": payload.get("is_inherited", False),
                "source_type": payload.get("source_type"),
                "origin_profile_name": payload.get("origin_profile_name"),
                "origin_profile_id": payload.get("origin_profile_id"),
            }
        return badges

    def run_summaries(
        self,
        *,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Aggregate lifecycle and harvest data into per-run summaries."""

        def _ensure(run_id: str) -> dict[str, Any]:
            summary = summaries.get(run_id)
            if summary is None:
                summary = {
                    "run_id": run_id,
                    "status": "unknown",
                    "started_at": None,
                    "ended_at": None,
                    "targets_met": None,
                    "targets_total": None,
                    "success_rate": None,
                    "stress_events": None,
                    "harvest_count": 0,
                    "yield_grams": 0.0,
                    "environment": {},
                    "metadata": {},
                    "_start_ts": None,
                    "_end_ts": None,
                    "_area_sum": 0.0,
                    "_density_samples": [],
                }
                summaries[run_id] = summary
            return summary

        summaries: dict[str, dict[str, Any]] = {}
        now = now or datetime.now(tz=UTC)

        for event in self.run_history:
            run_id = event.run_id or "run"
            summary = _ensure(run_id)

            start_ts = _parse_timestamp(event.started_at)
            if start_ts is not None:
                prev = summary.get("_start_ts")
                if prev is None or start_ts < prev:
                    summary["_start_ts"] = start_ts
                    summary["started_at"] = start_ts.isoformat()

            end_ts = _parse_timestamp(event.ended_at)
            if end_ts is not None:
                prev_end = summary.get("_end_ts")
                if prev_end is None or end_ts > prev_end:
                    summary["_end_ts"] = end_ts
                    summary["ended_at"] = end_ts.isoformat()

            if event.targets_met is not None:
                try:
                    summary["targets_met"] = float(event.targets_met)
                except (TypeError, ValueError):
                    summary["targets_met"] = None
            if event.targets_total is not None:
                try:
                    summary["targets_total"] = float(event.targets_total)
                except (TypeError, ValueError):
                    summary["targets_total"] = None
            if event.success_rate is not None:
                try:
                    rate = float(event.success_rate)
                except (TypeError, ValueError):
                    rate = None
                if rate is not None:
                    if rate <= 1.0:
                        rate *= 100.0
                    summary["success_rate"] = round(rate, 3)
            if event.stress_events is not None:
                try:
                    summary["stress_events"] = int(event.stress_events)
                except (TypeError, ValueError):
                    summary["stress_events"] = None
            if event.environment:
                env = summary.setdefault("environment", {})
                env.update(event.environment)
            if event.metadata:
                meta = summary.setdefault("metadata", {})
                meta.update(event.metadata)

        for index, harvest in enumerate(self.harvest_history):
            run_id = harvest.run_id or (self.run_history[-1].run_id if self.run_history else None)
            if not run_id:
                base_id = harvest.harvest_id or harvest.harvested_at or f"harvest-{index}"
                candidate = str(base_id).strip()
                if not candidate:
                    candidate = f"harvest-{index}"
                unique_id = candidate
                suffix = 1
                while unique_id in summaries:
                    suffix += 1
                    unique_id = f"{candidate}-{suffix}"
                run_id = unique_id
            summary = _ensure(run_id)
            summary["harvest_count"] = int(summary.get("harvest_count", 0)) + 1
            summary["yield_grams"] = float(summary.get("yield_grams", 0.0)) + float(harvest.yield_grams or 0.0)

            harvested_ts = _parse_timestamp(harvest.harvested_at)
            if harvested_ts is not None and summary.get("_start_ts") is None:
                summary["_start_ts"] = harvested_ts
                summary["started_at"] = harvested_ts.isoformat()
            if harvested_ts is not None:
                existing_end = summary.get("_end_ts")
                if existing_end is None or harvested_ts > existing_end:
                    summary["_end_ts"] = harvested_ts
                    summary["ended_at"] = harvested_ts.isoformat()

            if harvest.area_m2:
                try:
                    area = float(harvest.area_m2)
                except (TypeError, ValueError):
                    area = None
                if area is not None and area > 0:
                    summary["_area_sum"] = float(summary.get("_area_sum", 0.0)) + area
            density = harvest.yield_density()
            if density is not None:
                summary.setdefault("_density_samples", []).append(float(density))

        ordered = sorted(
            summaries.values(),
            key=lambda item: item.get("_start_ts") or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

        results: list[dict[str, Any]] = []
        for summary in ordered:
            start_ts: datetime | None = summary.pop("_start_ts", None)
            end_ts: datetime | None = summary.pop("_end_ts", None)
            area_sum = float(summary.pop("_area_sum", 0.0))
            densities: list[float] = summary.pop("_density_samples", [])

            if start_ts is not None:
                summary["started_at"] = start_ts.isoformat()
            if end_ts is not None:
                summary["ended_at"] = end_ts.isoformat()

            if start_ts is not None:
                effective_end = end_ts or now
                delta = max((effective_end - start_ts).total_seconds(), 0.0)
                summary["duration_days"] = round(delta / 86400, 3)
            else:
                summary["duration_days"] = None

            if end_ts is None and start_ts is not None:
                summary["status"] = "active"
            elif end_ts is not None and start_ts is not None:
                summary["status"] = "completed" if end_ts <= now else "pending"
            else:
                summary["status"] = summary.get("status") or "unknown"

            total_yield = float(summary.get("yield_grams", 0.0))
            summary["yield_grams"] = round(total_yield, 3) if total_yield else 0.0

            if area_sum > 0:
                summary["area_m2"] = round(area_sum, 3)
                if total_yield:
                    summary["yield_density_g_m2"] = round(total_yield / area_sum, 3)
            if densities:
                summary["mean_yield_density_g_m2"] = round(sum(densities) / len(densities), 3)

            targets_total = summary.get("targets_total")
            targets_met = summary.get("targets_met")
            if summary.get("success_rate") is None and targets_total and targets_met is not None:
                try:
                    summary["success_rate"] = round((float(targets_met) / float(targets_total)) * 100.0, 3)
                except (TypeError, ValueError):
                    summary["success_rate"] = None

            if not summary.get("environment"):
                summary.pop("environment", None)
            if not summary.get("metadata"):
                summary.pop("metadata", None)

            results.append(summary)

        if limit is not None:
            return results[:limit]
        return results

    def event_feed(
        self,
        *,
        now: datetime | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return chronological cultivation events with derived metadata."""

        entries: list[tuple[datetime | None, dict[str, Any]]] = []
        now = now or datetime.now(tz=UTC)
        for event in self.event_history:
            meta = event.summary()
            meta["event_type"] = event.event_type
            if event.run_id:
                meta["run_id"] = event.run_id
            if event.species_id:
                meta["species_id"] = event.species_id
            ts = _parse_timestamp(event.occurred_at)
            if ts is not None:
                meta["occurred_at"] = ts.isoformat()
                delta = max((now - ts).total_seconds() / 86400, 0.0)
                meta["days_since"] = round(delta, 3)
            else:
                meta["occurred_at"] = event.occurred_at
            entries.append((ts, meta))

        entries.sort(key=lambda item: item[0] or datetime.min.replace(tzinfo=UTC), reverse=True)

        feed = [item[1] for item in entries]
        if limit is not None:
            return feed[:limit]
        return feed

    def add_cultivation_event(self, event: CultivationEvent) -> None:
        """Append a cultivation event to the local event history."""

        normalised = CultivationEvent.from_json(event.to_json())
        if not normalised.profile_id:
            normalised.profile_id = self.profile_id
        if not normalised.species_id and self.species_profile_id:
            normalised.species_id = self.species_profile_id
        if normalised.run_id is None and self.run_history:
            normalised.run_id = self.run_history[-1].run_id
        self.event_history.append(normalised)

    def add_run_event(self, event: RunEvent) -> None:
        """Append a normalised run event to the local history."""

        normalised = RunEvent.from_json(event.to_json())
        if not normalised.profile_id:
            normalised.profile_id = self.profile_id
        if not normalised.species_id and self.species_profile_id:
            normalised.species_id = self.species_profile_id
        self.run_history.append(normalised)

    def add_harvest_event(self, event: HarvestEvent) -> None:
        """Append a harvest event and keep identifiers consistent."""

        normalised = HarvestEvent.from_json(event.to_json())
        if not normalised.profile_id:
            normalised.profile_id = self.profile_id
        if not normalised.species_id and self.species_profile_id:
            normalised.species_id = self.species_profile_id
        if normalised.run_id is None and self.run_history:
            normalised.run_id = self.run_history[-1].run_id
        self.harvest_history.append(normalised)

    def add_nutrient_event(self, event: NutrientApplication) -> None:
        """Append a nutrient event ensuring identifiers and defaults."""

        normalised = NutrientApplication.from_json(event.to_json())
        if not normalised.profile_id:
            normalised.profile_id = self.profile_id
        if not normalised.species_id and self.species_profile_id:
            normalised.species_id = self.species_profile_id
        if normalised.run_id is None and self.run_history:
            normalised.run_id = self.run_history[-1].run_id
        self.nutrient_history.append(normalised)

    def to_json(self) -> dict[str, Any]:
        resolved_payload = {key: value.to_json() for key, value in self.resolved_targets.items()}
        variables_payload = {key: value.to_legacy() for key, value in self.resolved_targets.items()}
        thresholds_payload = self.resolved_values()
        provenance_payload = self.resolved_provenance()

        sections = self._ensure_sections()
        library_section = sections.library
        local_section = sections.local

        payload = {
            "profile_id": self.profile_id,
            "plant_id": self.profile_id,
            "display_name": self.display_name,
            "profile_type": self.profile_type,
            "species": self.species,
            "tenant_id": self.tenant_id,
            "parents": list(self.parents),
            "identity": self.identity,
            "taxonomy": self.taxonomy,
            "policies": self.policies,
            "stable_knowledge": self.stable_knowledge,
            "lifecycle": self.lifecycle,
            "traits": self.traits,
            "tags": list(self.tags),
            "curated_targets": self.curated_targets,
            "diffs_vs_parent": self.diffs_vs_parent,
            "local_overrides": self.local_overrides,
            "resolver_state": self.resolver_state,
            "resolved_targets": resolved_payload,
            "variables": variables_payload,
            "thresholds": thresholds_payload,
            "resolved_provenance": provenance_payload,
            "computed_stats": [snapshot.to_json() for snapshot in self.computed_stats],
            "general": self.general,
            "citations": [asdict(cit) for cit in self.citations],
            "event_history": [event.to_json() for event in self.event_history],
            "run_history": [event.to_json() for event in self.run_history],
            "harvest_history": [event.to_json() for event in self.harvest_history],
            "nutrient_history": [event.to_json() for event in self.nutrient_history],
            "statistics": [stat.to_json() for stat in self.statistics],
            "last_resolved": self.last_resolved,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

        if self.library_metadata:
            payload["library_metadata"] = self.library_metadata
        if self.library_created_at is not None:
            payload["library_created_at"] = self.library_created_at
        if self.library_updated_at is not None:
            payload["library_updated_at"] = self.library_updated_at
        if self.local_metadata:
            payload["local_metadata"] = self.local_metadata

        payload["library"] = library_section.to_json()
        payload["local"] = local_section.to_json()
        payload["sections"] = sections.to_json()
        if self.lineage:
            payload["lineage"] = [entry.to_json() for entry in self.lineage]

        return payload

    def summary(self) -> dict[str, Any]:
        """Return a lightweight summary of the profile."""

        sensors = self.general.get("sensors")
        sensor_summary = dict(sensors) if isinstance(sensors, dict) else {}
        success_snapshot = next(
            (snap for snap in self.computed_stats if snap.stats_version == "success/v1"),
            None,
        )
        success_section: dict[str, Any] | None = None
        if success_snapshot is not None:
            payload = success_snapshot.payload if isinstance(success_snapshot.payload, dict) else {}
            success_section = {
                "weighted_percent": payload.get("weighted_success_percent"),
                "average_percent": payload.get("average_success_percent"),
                "best_percent": payload.get("best_success_percent"),
                "worst_percent": payload.get("worst_success_percent"),
                "runs_tracked": payload.get("runs_tracked"),
                "samples_recorded": payload.get("samples_recorded"),
                "targets_met": payload.get("targets_met"),
                "targets_total": payload.get("targets_total"),
                "stress_events": payload.get("stress_events"),
                "computed_at": success_snapshot.computed_at,
            }
            contributors = payload.get("contributors")
            if isinstance(contributors, list) and contributors:
                success_section["contributors"] = contributors
            success_section = {key: value for key, value in success_section.items() if value is not None}
            if not success_section:
                success_section = None

        summary: dict[str, Any] = {
            "profile_id": self.profile_id,
            "plant_id": self.profile_id,
            "name": self.display_name,
            "profile_type": self.profile_type,
            "species": self.species,
            "tenant_id": self.tenant_id,
            "parents": list(self.parents),
            "sensors": sensor_summary,
            "targets": self.resolved_values(),
            "provenance": self.provenance_summary(),
            "tags": list(self.tags),
            "last_resolved": self.last_resolved,
        }
        badge_map = self.provenance_badges()
        if badge_map:
            summary["provenance_badges"] = badge_map
        if success_section is not None:
            summary["success"] = success_section
        nutrient_snapshot = next(
            (snap for snap in self.computed_stats if snap.stats_version == "nutrients/v1"),
            None,
        )
        if nutrient_snapshot is not None:
            payload = nutrient_snapshot.payload if isinstance(nutrient_snapshot.payload, dict) else {}
            if payload:
                summary["nutrients"] = payload
        run_snapshots = self.run_summaries()
        if run_snapshots:
            summary["runs"] = {
                "total": len(run_snapshots),
                "active": [item["run_id"] for item in run_snapshots if item.get("status") == "active"],
                "recent": run_snapshots[:3],
                "latest": run_snapshots[0],
            }
        events = self.event_feed(limit=5)
        if events:
            summary["events"] = {
                "total": len(self.event_history),
                "recent": events[:5],
                "latest": events[0],
            }
        return summary

    @staticmethod
    def from_json(data: dict[str, Any]) -> BioProfile:
        """Create a BioProfile from a dictionary."""

        fallback_id = data.get("profile_id") or data.get("plant_id") or data.get("name") or "profile"
        profile_id = str(fallback_id)

        sections_payload = data.get("sections")
        sections = (
            ProfileSections.from_json(sections_payload, fallback_id=profile_id)
            if isinstance(sections_payload, Mapping)
            else None
        )

        if sections is not None:
            library_section = sections.library
            local_section = sections.local
            resolved_section = sections.resolved
            computed_section = sections.computed
        else:
            library_payload = data.get("library")
            library_section = (
                ProfileLibrarySection.from_json(library_payload, fallback_id=profile_id)
                if isinstance(library_payload, Mapping)
                else None
            )
            local_payload = data.get("local")
            local_section = ProfileLocalSection.from_json(local_payload) if isinstance(local_payload, Mapping) else None
            resolved_section = None
            computed_section = None

        if library_section:
            profile_type = str(library_section.profile_type or "line")
        else:
            profile_type = str(data.get("profile_type") or "line")

        resolved_targets: dict[str, ResolvedTarget] = {}
        if resolved_section is not None:
            resolved_source = resolved_section.resolved_targets
        else:
            resolved_source = (
                data.get("resolved_targets") if isinstance(data.get("resolved_targets"), Mapping) else None
            )
        if resolved_source:
            for key, value in resolved_source.items():
                if isinstance(value, ResolvedTarget):
                    resolved_targets[str(key)] = value
                elif isinstance(value, Mapping):
                    resolved_targets[str(key)] = ResolvedTarget.from_json(dict(value))

        if resolved_section is not None:
            legacy_variables = resolved_section.variables
        elif isinstance(data.get("variables"), Mapping):
            legacy_variables = data.get("variables")
        else:
            legacy_variables = None
        if isinstance(legacy_variables, Mapping):
            for key, value in legacy_variables.items():
                key_str = str(key)
                if key_str in resolved_targets or not isinstance(value, Mapping):
                    continue
                annotation = FieldAnnotation(source_type=value.get("source") or "unknown")
                citations = [Citation(**cit) for cit in value.get("citations", []) if isinstance(cit, Mapping)]
                resolved_targets[key_str] = ResolvedTarget(
                    value=value.get("value"),
                    annotation=annotation,
                    citations=citations,
                )

        if resolved_section is not None:
            legacy_thresholds = resolved_section.thresholds
        elif isinstance(data.get("thresholds"), Mapping):
            legacy_thresholds = data.get("thresholds")
        else:
            legacy_thresholds = None
        if isinstance(legacy_thresholds, Mapping):
            for key, value in legacy_thresholds.items():
                key_str = str(key)
                if key_str in resolved_targets:
                    continue
                annotation = FieldAnnotation(source_type="unknown")
                resolved_targets[key_str] = ResolvedTarget(value=value, annotation=annotation, citations=[])

        top_level_citations = [Citation(**cit) for cit in data.get("citations", []) if isinstance(cit, dict)]
        citations = list(local_section.citations) if local_section and local_section.citations else top_level_citations

        if computed_section is not None:
            computed_stats = list(computed_section.snapshots)
        else:
            computed_stats = [
                ComputedStatSnapshot.from_json(item)
                for item in data.get("computed_stats", []) or []
                if isinstance(item, dict)
            ]

        if library_section:
            parents = list(library_section.parents)
            tags = list(library_section.tags)
            identity = library_section.identity
            taxonomy = library_section.taxonomy
            policies = library_section.policies
            stable_knowledge = library_section.stable_knowledge
            lifecycle = library_section.lifecycle
            traits = library_section.traits
            curated_targets = library_section.curated_targets
            diffs_vs_parent = library_section.diffs_vs_parent
            tenant_id = library_section.tenant_id
            library_metadata = library_section.metadata
            library_created_at = library_section.created_at
            library_updated_at = library_section.updated_at
        else:
            parents_raw = data.get("parents") or []
            parents = [parents_raw] if isinstance(parents_raw, str) else [str(parent) for parent in parents_raw]
            tags_raw = data.get("tags") or []
            tags = [tags_raw] if isinstance(tags_raw, str) else [str(tag) for tag in tags_raw]
            identity = _as_dict(data.get("identity"))
            taxonomy = _as_dict(data.get("taxonomy"))
            policies = _as_dict(data.get("policies"))
            stable_knowledge = _as_dict(data.get("stable_knowledge"))
            lifecycle = _as_dict(data.get("lifecycle"))
            traits = _as_dict(data.get("traits"))
            curated_targets = _as_dict(data.get("curated_targets"))
            diffs_vs_parent = _as_dict(data.get("diffs_vs_parent"))
            tenant_id = data.get("tenant_id")
            library_metadata = _as_dict(data.get("library_metadata"))
            library_created_at = data.get("library_created_at")
            library_updated_at = data.get("library_updated_at")

        if local_section:
            species = local_section.species
            general = local_section.general
            local_overrides = local_section.local_overrides
            resolver_state = local_section.resolver_state
            last_resolved = local_section.last_resolved
            created_at = local_section.created_at
            updated_at = local_section.updated_at
            local_metadata = dict(local_section.metadata)
            event_history = list(local_section.event_history)
            run_history = list(local_section.run_history)
            harvest_history = list(local_section.harvest_history)
            nutrient_history = list(local_section.nutrient_history)
            statistics = list(local_section.statistics)
        else:
            species = data.get("species")
            general = _as_dict(data.get("general"))
            local_overrides = _as_dict(data.get("local_overrides") or data.get("overrides"))
            resolver_state = _as_dict(data.get("resolver_state"))
            last_resolved = data.get("last_resolved")
            created_at = data.get("created_at")
            updated_at = data.get("updated_at")
            local_metadata = _as_dict(data.get("local_metadata"))
            event_history = [
                CultivationEvent.from_json(item)
                for item in data.get("event_history", []) or []
                if isinstance(item, Mapping)
            ]
            run_history = [
                RunEvent.from_json(item) for item in data.get("run_history", []) or [] if isinstance(item, Mapping)
            ]
            harvest_history = [
                HarvestEvent.from_json(item)
                for item in data.get("harvest_history", []) or []
                if isinstance(item, Mapping)
            ]
            nutrient_history = [
                NutrientApplication.from_json(item)
                for item in data.get("nutrient_history", []) or []
                if isinstance(item, Mapping)
            ]
            statistics = [
                YieldStatistic.from_json(item) for item in data.get("statistics", []) or [] if isinstance(item, Mapping)
            ]

        if resolved_section is not None:
            if resolved_section.metadata:
                local_metadata.update(resolved_section.metadata)
            if resolved_section.last_resolved and not last_resolved:
                last_resolved = resolved_section.last_resolved
            citation_map = resolved_section.citation_map
            if citation_map:
                local_metadata.setdefault("citation_map", dict(citation_map))
            provenance_map = resolved_section.provenance_map
            if provenance_map:
                local_metadata.setdefault("provenance_map", dict(provenance_map))

        extra_kwargs: dict[str, Any] = {}
        if profile_type == "species":
            profile_cls: type[BioProfile] = SpeciesProfile
            cultivar_ids_raw = data.get("cultivar_ids")
            if not isinstance(cultivar_ids_raw, list):
                cultivar_ids_raw = local_metadata.get("cultivar_ids") if isinstance(local_metadata, Mapping) else []
            cultivar_ids: list[str] = []
            if isinstance(cultivar_ids_raw, list):
                for item in cultivar_ids_raw:
                    cultivar_ids.append(str(item))
            extra_kwargs["cultivar_ids"] = cultivar_ids
        elif profile_type in {"cultivar", "line"}:
            profile_cls = CultivarProfile
            area = data.get("area_m2")
            if area is None:
                meta_area = local_metadata.get("area_m2") if isinstance(local_metadata, Mapping) else None
                area = meta_area
            try:
                extra_kwargs["area_m2"] = float(area) if area is not None else None
            except (TypeError, ValueError):
                extra_kwargs["area_m2"] = None
        else:
            profile_cls = BioProfile

        profile = profile_cls(
            profile_id=profile_id,
            display_name=data.get("display_name") or data.get("name") or profile_id,
            profile_type=profile_type,
            species=species,
            tenant_id=tenant_id,
            parents=parents,
            identity=identity,
            taxonomy=taxonomy,
            policies=policies,
            stable_knowledge=stable_knowledge,
            lifecycle=lifecycle,
            traits=traits,
            tags=tags,
            curated_targets=curated_targets,
            diffs_vs_parent=diffs_vs_parent,
            library_metadata=library_metadata,
            library_created_at=library_created_at,
            library_updated_at=library_updated_at,
            local_overrides=local_overrides,
            resolver_state=resolver_state,
            resolved_targets=resolved_targets,
            computed_stats=computed_stats,
            general=general,
            citations=citations,
            local_metadata=local_metadata,
            run_history=run_history,
            harvest_history=harvest_history,
            nutrient_history=nutrient_history,
            statistics=statistics,
            last_resolved=last_resolved,
            created_at=created_at,
            updated_at=updated_at,
            sections=sections,
            lineage=[
                ProfileLineageEntry.from_json(item) for item in data.get("lineage", []) if isinstance(item, Mapping)
            ],
            **extra_kwargs,
        )

        profile.event_history = list(event_history)

        return profile

    # ------------------------------------------------------------------
    def library_section(self) -> ProfileLibrarySection:
        return ProfileLibrarySection(
            profile_id=self.profile_id,
            profile_type=self.profile_type,
            tenant_id=self.tenant_id,
            identity=dict(self.identity),
            taxonomy=dict(self.taxonomy),
            parents=list(self.parents),
            policies=dict(self.policies),
            stable_knowledge=dict(self.stable_knowledge),
            lifecycle=dict(self.lifecycle),
            traits=dict(self.traits),
            curated_targets=dict(self.curated_targets),
            diffs_vs_parent=dict(self.diffs_vs_parent),
            tags=list(self.tags),
            metadata=dict(self.library_metadata),
            created_at=self.library_created_at,
            updated_at=self.library_updated_at,
        )

    def local_section(self) -> ProfileLocalSection:
        return ProfileLocalSection(
            species=self.species,
            general=dict(self.general),
            local_overrides=dict(self.local_overrides),
            resolver_state=dict(self.resolver_state),
            citations=[Citation(**asdict(cit)) for cit in self.citations],
            event_history=[CultivationEvent.from_json(event.to_json()) for event in self.event_history],
            run_history=[RunEvent.from_json(event.to_json()) for event in self.run_history],
            harvest_history=[HarvestEvent.from_json(event.to_json()) for event in self.harvest_history],
            nutrient_history=[NutrientApplication.from_json(event.to_json()) for event in self.nutrient_history],
            statistics=[YieldStatistic.from_json(stat.to_json()) for stat in self.statistics],
            last_resolved=self.last_resolved,
            created_at=self.created_at,
            updated_at=self.updated_at,
            metadata=dict(self.local_metadata),
        )

    def resolved_section(self) -> ProfileResolvedSection:
        resolved_targets = dict(self.resolved_targets)
        thresholds = self.resolved_values()
        variables = {key: target.to_legacy() for key, target in resolved_targets.items()}
        metadata = dict(self.local_metadata)
        citation_map = {}
        raw_citation_map = metadata.get("citation_map") if isinstance(metadata.get("citation_map"), Mapping) else None
        if isinstance(raw_citation_map, Mapping):
            citation_map = dict(raw_citation_map)
        return ProfileResolvedSection(
            thresholds=thresholds,
            resolved_targets=resolved_targets,
            variables=variables,
            citation_map=citation_map,
            metadata=metadata,
            provenance_map=self.provenance_summary(),
            last_resolved=self.last_resolved,
        )

    def computed_section(self) -> ProfileComputedSection:
        snapshots = list(self.computed_stats)
        latest = snapshots[0] if snapshots else None
        contributions: list[ProfileContribution] = []
        if latest:
            contributions = list(latest.contributions)
        return ProfileComputedSection(
            snapshots=snapshots,
            latest=latest,
            contributions=contributions,
            metadata={},
        )

    def refresh_sections(self) -> ProfileSections:
        """Refresh cached :class:`ProfileSections` to match current fields."""

        library = self.library_section()
        local = self.local_section()
        resolved = self.resolved_section()
        computed = self.computed_section()

        if self.sections is None:
            self.sections = ProfileSections(
                library=library,
                local=local,
                resolved=resolved,
                computed=computed,
            )
            return self.sections

        existing = self.sections

        merged_resolved_metadata = dict(existing.resolved.metadata)
        merged_resolved_metadata.update(resolved.metadata)
        resolved.metadata = merged_resolved_metadata

        merged_citation_map = dict(existing.resolved.citation_map)
        if resolved.citation_map:
            merged_citation_map.update(resolved.citation_map)
        resolved.citation_map = merged_citation_map

        merged_provenance_map = dict(existing.resolved.provenance_map)
        if resolved.provenance_map:
            merged_provenance_map.update(resolved.provenance_map)
        resolved.provenance_map = merged_provenance_map

        merged_computed_metadata = dict(existing.computed.metadata)
        merged_computed_metadata.update(computed.metadata)
        computed.metadata = merged_computed_metadata

        if computed.latest is None and existing.computed.latest is not None:
            computed.latest = existing.computed.latest
        if not computed.snapshots and existing.computed.snapshots:
            computed.snapshots = list(existing.computed.snapshots)
        if not computed.contributions and existing.computed.contributions:
            computed.contributions = list(existing.computed.contributions)

        existing.library = library
        existing.local = local
        existing.resolved = resolved
        existing.computed = computed
        self.sections = existing
        return self.sections

    def _ensure_sections(self) -> ProfileSections:
        return self.refresh_sections()

    @property
    def local(self) -> ProfileLocalSection:
        """Return the cached local section, refreshing when necessary."""

        return self.refresh_sections().local

    @local.setter
    def local(self, value: ProfileLocalSection | Mapping[str, Any]) -> None:
        """Replace the local section from a section object or raw mapping."""

        if isinstance(value, ProfileLocalSection):
            section = value
        elif isinstance(value, Mapping):
            section = ProfileLocalSection.from_json(value)
        else:  # pragma: no cover - defensive type guard
            raise TypeError("local section must be a ProfileLocalSection or mapping")

        self.species = section.species
        self.general = dict(section.general)
        self.local_overrides = dict(section.local_overrides)
        self.resolver_state = dict(section.resolver_state)
        self.citations = [Citation(**asdict(cit)) for cit in section.citations]
        self.event_history = [CultivationEvent.from_json(event.to_json()) for event in section.event_history]
        self.run_history = [RunEvent.from_json(event.to_json()) for event in section.run_history]
        self.harvest_history = [HarvestEvent.from_json(event.to_json()) for event in section.harvest_history]
        self.nutrient_history = [NutrientApplication.from_json(event.to_json()) for event in section.nutrient_history]
        self.statistics = [YieldStatistic.from_json(stat.to_json()) for stat in section.statistics]
        self.local_metadata = dict(section.metadata)
        self.last_resolved = section.last_resolved
        self.created_at = section.created_at
        self.updated_at = section.updated_at
        self.refresh_sections()


@dataclass
class SpeciesProfile(BioProfile):
    """Represents a species-level BioProfile that can be inherited from."""

    profile_type: str = "species"
    cultivar_ids: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.species:
            self.species = self.profile_id

    def to_json(self) -> dict[str, Any]:
        payload = super().to_json()
        payload["profile_type"] = "species"
        if self.cultivar_ids:
            payload["cultivar_ids"] = list({str(cid) for cid in self.cultivar_ids})
        return payload


@dataclass
class CultivarProfile(BioProfile):
    """Represents a cultivar profile inheriting from a species entry."""

    profile_type: str = "cultivar"
    area_m2: float | None = None

    def to_json(self) -> dict[str, Any]:
        payload = super().to_json()
        payload["profile_type"] = "cultivar"
        if self.area_m2 is not None:
            payload["area_m2"] = self.area_m2
        return payload
