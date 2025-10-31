from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector as sel
from homeassistant.util import slugify

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CLOUD_BASE_URL,
    CONF_CLOUD_DEVICE_TOKEN,
    CONF_CLOUD_SYNC_ENABLED,
    CONF_CLOUD_SYNC_INTERVAL,
    CONF_CLOUD_TENANT_ID,
    CONF_CO2_SENSOR,
    CONF_EC_SENSOR,
    CONF_KEEP_STALE,
    CONF_MODEL,
    CONF_MOISTURE_SENSOR,
    CONF_PLANT_ID,
    CONF_PLANT_NAME,
    CONF_PLANT_TYPE,
    CONF_PROFILE_SCOPE,
    CONF_PROFILES,
    CONF_TEMPERATURE_SENSOR,
    CONF_UPDATE_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_CLOUD_SYNC_INTERVAL,
    DEFAULT_KEEP_STALE,
    DEFAULT_MODEL,
    DEFAULT_UPDATE_MINUTES,
    DOMAIN,
    PROFILE_SCOPE_CHOICES,
    PROFILE_SCOPE_DEFAULT,
)
from .opb_client import OpenPlantbookClient
from .profile.compat import sync_thresholds
from .profile.utils import determine_species_slug, ensure_sections
from .profile.validation import evaluate_threshold_bounds
from .profile_store import ProfileStore
from .sensor_catalog import SensorSuggestion, collect_sensor_suggestions, format_sensor_hints
from .sensor_validation import collate_issue_messages, validate_sensor_links
from .utils import profile_generator
from .utils.entry_helpers import get_entry_data, get_primary_profile_id
from .utils.json_io import load_json, save_json
from .utils.nutrient_schedule import generate_nutrient_schedule
from .utils.plant_registry import register_plant

_LOGGER = logging.getLogger(__name__)

PROFILE_SCOPE_LABELS = {
    "individual": "Individual plant (single specimen)",
    "species_template": "Species template (reusable baseline)",
    "crop_batch": "Crop batch or bed (shared conditions)",
    "grow_zone": "Grow zone or environment",
}
SOURCE_FILTER_SYNONYMS = {
    "entry": {"entry", "local", "existing", "installed", "profile"},
    "library": {"library", "lib", "template", "catalog", "store"},
}
SOURCE_FILTER_LABELS = {
    "entry": "Existing entries",
    "library": "Library templates",
}
SCOPE_FILTER_SYNONYMS = {
    "individual": {"individual", "plant", "single"},
    "species_template": {"species_template", "species", "template", "baseline"},
    "crop_batch": {"crop_batch", "batch", "crop", "bed"},
    "grow_zone": {"grow_zone", "zone", "environment", "room"},
}
PROFILE_SCOPE_SELECTOR_OPTIONS = [
    {"value": value, "label": PROFILE_SCOPE_LABELS[value]} for value in PROFILE_SCOPE_CHOICES
]

MANUAL_THRESHOLD_FIELDS = (
    "temperature_min",
    "temperature_max",
    "humidity_min",
    "humidity_max",
    "illuminance_min",
    "illuminance_max",
    "conductivity_min",
    "conductivity_max",
)


SENSOR_OPTION_ROLES = {
    CONF_MOISTURE_SENSOR: "moisture",
    CONF_TEMPERATURE_SENSOR: "temperature",
    CONF_EC_SENSOR: "ec",
    CONF_CO2_SENSOR: "co2",
}

SENSOR_OPTION_FALLBACKS = {
    CONF_MOISTURE_SENSOR: sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])),
    CONF_TEMPERATURE_SENSOR: sel.EntitySelector(
        sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])
    ),
    CONF_EC_SENSOR: sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"])),
    CONF_CO2_SENSOR: sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["carbon_dioxide"])),
}

PROFILE_SENSOR_FIELDS = {
    "temperature": sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])),
    "humidity": sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["humidity"])),
    "illuminance": sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["illuminance"])),
    "moisture": sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])),
    "conductivity": sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"])),
    "co2": sel.EntitySelector(sel.EntitySelectorConfig(domain=["sensor"], device_class=["carbon_dioxide"])),
}


def _derive_fallback_plant_id(name: str, plant_type: str | None = None) -> str | None:
    """Return a slugified identifier derived from ``name`` or ``plant_type``."""

    for candidate in (name, plant_type or ""):
        if not candidate:
            continue
        slug = slugify(candidate)
        if slug:
            return slug
    return None


def _normalise_sensor_submission(value: Any) -> str | list[str] | None:
    """Return a cleaned representation of sensor input from the config flow."""

    if value is None:
        return None
    if isinstance(value, str):
        entity_id = value.strip()
        return entity_id or None
    if isinstance(value, Mapping):
        collected: list[str] = []
        for key in ("entity_id", "value", "id", "option", "name"):
            candidate = value.get(key)
            cleaned = _normalise_sensor_submission(candidate)
            if cleaned is None:
                continue
            if isinstance(cleaned, list):
                collected.extend(cleaned)
            else:
                collected.append(cleaned)
        if not collected:
            for candidate in value.values():
                cleaned = _normalise_sensor_submission(candidate)
                if cleaned is None:
                    continue
                if isinstance(cleaned, list):
                    collected.extend(cleaned)
                else:
                    collected.append(cleaned)
        if not collected:
            return None
        if len(collected) == 1:
            return collected[0]
        return collected
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        entries: list[str] = []
        for item in value:
            if isinstance(item, str):
                cleaned = item.strip()
            elif item is None:
                cleaned = ""
            else:
                cleaned = str(item).strip()
            if cleaned:
                entries.append(cleaned)
        if entries:
            return entries
        return None
    text = str(value).strip()
    return text or None


def _default_sensor_value(value: Any) -> Any:
    """Return the default value to use for a profile sensor field."""

    normalised = _normalise_sensor_submission(value)
    if normalised is None:
        return vol.UNDEFINED
    if isinstance(normalised, list):
        return list(normalised)
    return normalised


def _select_sensor_value(value: Any) -> str | None:
    """Return a single sensor entity id extracted from ``value``."""

    normalised = _normalise_sensor_submission(value)
    if isinstance(normalised, list):
        return normalised[0] if normalised else None
    return normalised


def _coerce_validation_items(payload: Any, attribute: str) -> list[Any]:
    """Return a list of validation issues extracted from ``payload``."""

    container: Any = None

    try:
        container = getattr(payload, attribute)
    except AttributeError:
        if isinstance(payload, Mapping):
            container = payload.get(attribute)
    except Exception:  # pragma: no cover - defensive guard
        return []

    if container is None:
        return []

    if isinstance(container, Mapping):
        return [item for item in container.values() if item is not None]

    if isinstance(container, Sequence) and not isinstance(container, str | bytes | bytearray):
        return [item for item in container if item is not None]

    try:
        return [item for item in list(container) if item is not None]
    except TypeError:
        return []
    except Exception:  # pragma: no cover - defensive guard
        return []


def _issue_role(issue: Any) -> str | None:
    """Return the sensor role encoded in ``issue`` when available."""

    candidate = issue.get("role") if isinstance(issue, Mapping) else getattr(issue, "role", None)
    if isinstance(candidate, str):
        cleaned = candidate.strip()
        return cleaned or None
    return None


def _issue_code(issue: Any) -> str:
    """Return the validation code encoded in ``issue``."""
    if isinstance(issue, Mapping):
        for key in ("issue", "code", "error"):
            value = issue.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    else:
        for attr in ("issue", "code", "error"):
            value = getattr(issue, attr, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return "invalid_sensor"


def _filter_sensor_warning_payload(items: Sequence[Any]) -> list[Any]:
    """Return a list of sensor warning issues safe to notify about."""

    filtered: list[Any] = []
    for issue in items:
        if isinstance(issue, Mapping):
            role = issue.get("role")
            entity_id = issue.get("entity_id")
            code = issue.get("issue")
        else:
            role = getattr(issue, "role", None)
            entity_id = getattr(issue, "entity_id", None)
            code = getattr(issue, "issue", None)
        if isinstance(role, str) and isinstance(entity_id, str) and isinstance(code, str):
            filtered.append(issue)
    return filtered


def _coerce_threshold_source_method(value: Any) -> str:
    """Best-effort conversion of selector submissions to a method string."""

    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, Mapping):
        for key in ("value", "id", "option", "method", "name"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                cleaned = candidate.strip()
                if cleaned:
                    return cleaned
        for candidate in value.values():
            if isinstance(candidate, str):
                cleaned = candidate.strip()
                if cleaned:
                    return cleaned

    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            cleaned = _coerce_threshold_source_method(item)
            if cleaned:
                return cleaned

    return str(value).strip()


def _build_manual_threshold_payload(thresholds: Mapping[str, Any], *, source: str = "manual") -> dict[str, Any]:
    """Return a minimal resolved payload using ``thresholds`` and ``source``."""

    cleaned_thresholds = {str(key): value for key, value in thresholds.items()}

    resolved: dict[str, Any] = {}
    variables: dict[str, Any] = {}
    annotation = {"source_type": source, "method": source}

    for key, value in cleaned_thresholds.items():
        resolved[key] = {"value": value, "annotation": dict(annotation), "citations": []}
        variables[key] = {
            "value": value,
            "source": source,
            "annotation": dict(annotation),
        }

    sections = {
        "resolved": {
            "thresholds": dict(cleaned_thresholds),
            "resolved_targets": dict(resolved),
            "variables": dict(variables),
        }
    }

    return {
        "thresholds": dict(cleaned_thresholds),
        "resolved_targets": resolved,
        "variables": variables,
        "sections": sections,
    }


def _ensure_general_profile_file(
    path: str | Path,
    plant_id: str,
    display_name: str,
    plant_type: str | None,
    profile_scope: str | None,
    sensor_map: Mapping[str, Sequence[str]] | None,
) -> None:
    """Ensure ``path`` contains general profile metadata for ``plant_id``."""

    try:
        data = load_json(path)
    except Exception:
        data = {}

    if not isinstance(data, Mapping):
        data = {}

    changed = False

    if data.get("plant_id") != plant_id:
        data = dict(data)
        data["plant_id"] = plant_id
        changed = True
    else:
        data = dict(data)

    if display_name:
        existing_name = data.get("display_name")
        if not isinstance(existing_name, str) or not existing_name.strip() or existing_name.strip().upper() == "TBD":
            data["display_name"] = display_name
            changed = True

    if plant_type:
        slug = slugify(plant_type)
        existing_type = data.get("plant_type")
        if not isinstance(existing_type, str) or not existing_type.strip() or existing_type.strip().lower() == "tbd":
            data["plant_type"] = slug or plant_type
            changed = True

    if profile_scope and data.get(CONF_PROFILE_SCOPE) != profile_scope:
        data[CONF_PROFILE_SCOPE] = profile_scope
        changed = True

    if sensor_map:
        container = data.get("sensor_entities")
        if not isinstance(container, Mapping):
            container = {}
        updated_container: dict[str, list[str]] = dict(container)
        for key, values in sensor_map.items():
            cleaned_values = [str(item) for item in values if item is not None]
            if updated_container.get(key) != cleaned_values:
                updated_container[key] = cleaned_values
                changed = True
        if updated_container != container:
            data["sensor_entities"] = updated_container
            changed = True

    general_path = Path(path)
    if changed or not general_path.exists():
        save_json(general_path, data)  # type: ignore[arg-type]


def _has_registered_service(hass, domain: str, service: str) -> bool:
    """Return True if the service registry reports the given service."""

    services = getattr(hass, "services", None)
    if services is None:
        return False

    has_service = getattr(services, "has_service", None)
    if callable(has_service):
        try:
            return bool(has_service(domain, service))
        except TypeError:
            try:
                return bool(has_service(domain=domain, service=service))
            except TypeError:  # pragma: no cover - defensive
                return False

    async_services = getattr(services, "async_services", None)
    if callable(async_services):
        try:
            registered = async_services()
        except TypeError:
            try:
                registered = async_services(hass)
            except TypeError:  # pragma: no cover - defensive
                registered = None
        if isinstance(registered, Mapping):
            domain_services = registered.get(domain)
            if isinstance(domain_services, Mapping):
                return service in domain_services

    registered = getattr(services, "_services", None)
    if isinstance(registered, Mapping):
        domain_services = registered.get(domain)
        if isinstance(domain_services, Mapping):
            return service in domain_services

    return False


def _as_str(value: Any) -> str | None:
    """Return ``value`` as a stripped string when possible."""

    if value is None:
        return None
    if isinstance(value, str):
        candidate = value.strip()
        return candidate or None
    try:
        candidate = str(value).strip()
    except Exception:  # pragma: no cover - defensive guard
        return None
    return candidate or None


def _iter_sensor_values(value: Any) -> list[str]:
    """Return a list of potential sensor entity ids extracted from ``value``."""

    normalised = _normalise_sensor_submission(value)
    if normalised is None:
        return []
    if isinstance(normalised, list):
        return [item for item in normalised if isinstance(item, str) and item]
    if isinstance(normalised, str):
        cleaned = normalised.strip()
        return [cleaned] if cleaned else []
    return []


def _suggestion_attr(candidate: Any, key: str) -> Any:
    """Return attribute ``key`` from ``candidate`` handling mappings and objects."""

    if isinstance(candidate, Mapping):
        return candidate.get(key)
    try:
        return getattr(candidate, key)
    except AttributeError:
        return None
    except Exception:  # pragma: no cover - defensive guard
        return None


def _extract_suggestion_entity_id(candidate: Any) -> str | None:
    """Return an entity id extracted from ``candidate`` if available."""

    for key in ("entity_id", "entity", "id", "value", "option", "slug", "identifier", "unique_id"):
        raw = _suggestion_attr(candidate, key)
        for entry in _iter_sensor_values(raw):
            if entry:
                return entry
    if isinstance(candidate, Mapping):
        for raw in candidate.values():
            for entry in _iter_sensor_values(raw):
                if entry:
                    return entry
    if isinstance(candidate, Sequence) and not isinstance(candidate, str | bytes | bytearray):
        for item in candidate:
            for entry in _iter_sensor_values(item):
                if entry:
                    return entry
    for entry in _iter_sensor_values(candidate):
        if entry:
            return entry
    return None


def _is_valid_entity_id(entity_id: str | None) -> bool:
    """Return True if ``entity_id`` resembles a Home Assistant entity id."""

    if not entity_id:
        return False
    return "." in entity_id and not any(ch.isspace() for ch in entity_id)


def _extract_suggestion_name(candidate: Any, entity_id: str | None = None) -> str | None:
    """Return a friendly name extracted from ``candidate`` if available."""

    for key in ("name", "label", "title", "friendly_name", "display_name"):
        value = _suggestion_attr(candidate, key)
        text = _as_str(value)
        if text:
            return text
    if isinstance(candidate, Mapping):
        for value in candidate.values():
            text = _as_str(value)
            if text:
                return text
    if isinstance(candidate, Sequence) and not isinstance(candidate, str | bytes | bytearray):
        for item in candidate:
            text = _as_str(item)
            if text and (entity_id is None or text != entity_id):
                return text
    return _as_str(candidate)


def _extract_suggestion_score(candidate: Any) -> int:
    """Return an integer score extracted from ``candidate`` if present."""

    raw = _suggestion_attr(candidate, "score")
    if raw is None:
        return 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def _coerce_sensor_hint(candidate: Any) -> tuple[str, str, SensorSuggestion] | None:
    """Return sanitised entity id, friendly name, and hint object for ``candidate``."""

    if isinstance(candidate, SensorSuggestion):
        entity_id = _as_str(candidate.entity_id)
        if not _is_valid_entity_id(entity_id):
            return None
        name = _extract_suggestion_name(candidate, entity_id) or entity_id
        if entity_id != candidate.entity_id or name != candidate.name:
            candidate = SensorSuggestion(
                entity_id=entity_id,
                name=name,
                score=candidate.score,
                reason=candidate.reason,
            )
        return entity_id, name, candidate

    entity_id = _extract_suggestion_entity_id(candidate)
    if not _is_valid_entity_id(entity_id):
        return None
    name = _extract_suggestion_name(candidate, entity_id) or entity_id
    score = _extract_suggestion_score(candidate)
    reason = _as_str(_suggestion_attr(candidate, "reason")) or ""
    hint = SensorSuggestion(entity_id=entity_id, name=name, score=score, reason=reason)
    return entity_id, name, hint


def _normalise_sensor_suggestions(
    suggestions: Mapping[str, Any], role_names: Sequence[str]
) -> tuple[dict[str, list[SensorSuggestion]], dict[str, list[tuple[str, str]]]]:
    """Return sanitised hints and selector entries for ``suggestions``."""

    hint_map: dict[str, list[SensorSuggestion]] = {role: [] for role in role_names}
    selector_entries: dict[str, list[tuple[str, str]]] = {role: [] for role in role_names}

    for role in role_names:
        raw_entries = suggestions.get(role, [])
        if raw_entries is None:
            iterable: list[Any] = []
        elif isinstance(raw_entries, Mapping):
            try:
                iterable = list(raw_entries.values())
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.debug("Skipping sensor suggestions for role '%s': %s", role, err)
                iterable = []
        elif isinstance(raw_entries, str | bytes | bytearray):
            iterable = [raw_entries]
        elif isinstance(raw_entries, Sequence):
            try:
                iterable = list(raw_entries)
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.debug("Skipping sensor suggestions for role '%s': %s", role, err)
                iterable = []
        elif isinstance(raw_entries, Iterable):
            try:
                iterable = list(raw_entries)
            except TypeError:
                iterable = [raw_entries]
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.debug("Skipping sensor suggestions for role '%s': %s", role, err)
                iterable = []
        else:
            iterable = [raw_entries]

        seen: set[str] = set()
        for candidate in iterable:
            try:
                normalised = _coerce_sensor_hint(candidate)
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.debug("Skipping sensor suggestion for role '%s': %s", role, err)
                continue
            if normalised is None:
                continue
            entity_id, name, hint = normalised
            key = entity_id.casefold()
            if key in seen:
                continue
            seen.add(key)
            hint_map[role].append(hint)
            selector_entries[role].append((entity_id, name))

    return hint_map, selector_entries


def _build_sensor_schema(hass, defaults: Mapping[str, Any] | None = None):
    """Return a voluptuous schema and hint placeholders for sensor selection."""

    defaults = defaults or {}
    role_names = sorted(set(SENSOR_OPTION_ROLES.values()))
    try:
        suggestions = collect_sensor_suggestions(
            hass,
            SENSOR_OPTION_ROLES.values(),
            limit=6,
        )
    except Exception as err:  # pragma: no cover - exercised via regression test
        _LOGGER.warning("Unable to collect sensor suggestions: %s", err)
        suggestions = {}
    if not isinstance(suggestions, Mapping):
        suggestions = {}
    hint_map, selector_entries = _normalise_sensor_suggestions(suggestions, role_names)
    placeholders = {"sensor_hints": format_sensor_hints(hint_map)}

    schema_fields: dict[Any, Any] = {}
    for option_key, role in SENSOR_OPTION_ROLES.items():
        default_value = defaults.get(option_key)
        if default_value is None:
            optional = vol.Optional(option_key)
        else:
            optional = vol.Optional(option_key, default=default_value)
        options = selector_entries.get(role, [])
        if options:
            selector = sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=[
                        {
                            "value": entity_id,
                            "label": f"{name} ({entity_id})" if name and name != entity_id else entity_id,
                        }
                        for entity_id, name in options
                    ],
                    custom_value=True,
                )
            )
        else:
            selector = SENSOR_OPTION_FALLBACKS[option_key]
        schema_fields[optional] = vol.Any(selector, str)

    return vol.Schema(schema_fields), placeholders


def _normalize_source_filter(value: str) -> str | None:
    candidate = value.casefold().replace("-", "_")
    if candidate in {"all", "any", "*"}:
        return None
    for canonical, synonyms in SOURCE_FILTER_SYNONYMS.items():
        if candidate == canonical or candidate in synonyms:
            return canonical
    return None


def _normalize_scope_filter(value: str) -> str | None:
    candidate = value.casefold().replace("-", "_")
    if candidate in {"all", "any", "*"}:
        return None
    for canonical, synonyms in SCOPE_FILTER_SYNONYMS.items():
        if candidate == canonical or candidate in synonyms:
            return canonical
    return None


def _extract_profile_scope(profile: Mapping[str, Any]) -> str | None:
    raw_scope = profile.get(CONF_PROFILE_SCOPE)
    if isinstance(raw_scope, str):
        normalized = raw_scope.casefold()
        for option in PROFILE_SCOPE_CHOICES:
            if normalized == option:
                return option
    general = profile.get("general")
    if isinstance(general, Mapping):
        nested = general.get(CONF_PROFILE_SCOPE)
        if isinstance(nested, str):
            normalized = nested.casefold()
            for option in PROFILE_SCOPE_CHOICES:
                if normalized == option:
                    return option
    return None


def _parse_template_filter(value: str) -> tuple[list[str], set[str], set[str]]:
    search_terms: list[str] = []
    source_filters: set[str] = set()
    scope_filters: set[str] = set()
    for raw_token in value.split():
        if not raw_token:
            continue
        key, sep, raw_value = raw_token.partition(":")
        if sep:
            key_cf = key.casefold()
            trimmed_value = raw_value.strip()
            if trimmed_value:
                if key_cf == "source":
                    normalized = _normalize_source_filter(trimmed_value)
                    if normalized:
                        source_filters.add(normalized)
                        continue
                elif key_cf == "scope":
                    normalized = _normalize_scope_filter(trimmed_value)
                    if normalized:
                        scope_filters.add(normalized)
                        continue
        search_terms.append(raw_token)
    return search_terms, source_filters, scope_filters


def _normalize_template_source(value: str | None) -> str:
    if not value:
        return "entry"
    return str(value).split(":", 1)[0]


def _summarise_template_filters(
    search_terms: list[str],
    source_filters: set[str],
    scope_filters: set[str],
    visible_count: int,
    total_count: int,
) -> str:
    if not (search_terms or source_filters or scope_filters):
        return ""
    parts: list[str] = []
    if search_terms:
        parts.append(f"Text: \"{' '.join(search_terms)}\"")
    if source_filters:
        labels = sorted(SOURCE_FILTER_LABELS.get(item, item.title()) for item in source_filters)
        parts.append(f"Sources: {', '.join(labels)}")
    if scope_filters:
        labels = sorted(PROFILE_SCOPE_LABELS.get(item, item.replace('_', ' ').title()) for item in scope_filters)
        parts.append(f"Scopes: {', '.join(labels)}")
    summary = "Applied filters — " + "; ".join(parts)
    if total_count:
        summary += f". Showing {visible_count} of {total_count} templates."
    return summary


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[misc,call-arg]
    VERSION = 3

    def __init__(self) -> None:
        self._config: dict | None = None
        self._profile: dict | None = None
        self._thresholds: dict[str, float] = {}
        self._threshold_snapshot: dict[str, Any] | None = None
        self._opb_credentials: dict[str, str] | None = None
        self._opb_results: list[dict[str, str]] = []
        self._species_pid: str | None = None
        self._species_display: str | None = None
        self._image_url: str | None = None
        self._existing_entry: config_entries.ConfigEntry | None = None
        self._sensor_defaults: dict[str, str] | None = None
        self._profile_templates: dict[str, Mapping[str, Any]] | None = None
        self._profile_template_sources: dict[str, str] = {}
        self._profile_store: ProfileStore | None = None
        self._template_filter: str | None = None

    async def async_step_user(self, user_input=None):
        entries = self._async_current_entries()
        if entries:
            self._existing_entry = entries[0]
            return await self.async_step_post_setup(user_input)

        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Required("setup_mode", default="profile"): sel.SelectSelector(
                        sel.SelectSelectorConfig(
                            options=[
                                {
                                    "value": "profile",
                                    "label": "Create a plant profile now",
                                },
                                {
                                    "value": "skip",
                                    "label": "Skip for now (add profiles later)",
                                },
                            ]
                        )
                    )
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        setup_mode = user_input.get("setup_mode", "profile")
        if setup_mode == "skip":
            title = self.hass.config.location_name or "Horticulture Assistant"
            return self.async_create_entry(title=title, data={}, options={})

        self._config = {}
        self._reset_profile_context()
        return await self.async_step_profile()

    def _reset_profile_context(self) -> None:
        self._profile = None
        self._thresholds = {}
        self._threshold_snapshot = None
        self._opb_credentials = None
        self._opb_results = []
        self._species_pid = None
        self._species_display = None
        self._image_url = None
        self._sensor_defaults = None
        self._template_filter = None

    def _known_plant_ids(self) -> set[str]:
        """Return plant identifiers already assigned to existing profiles."""

        known: set[str] = set()

        def _collect(entry) -> None:
            if entry is None:
                return
            data_pid = entry.data.get(CONF_PLANT_ID)
            if isinstance(data_pid, str) and data_pid:
                known.add(data_pid)
            options = entry.options if isinstance(entry.options, Mapping) else {}
            opt_pid = options.get(CONF_PLANT_ID)
            if isinstance(opt_pid, str) and opt_pid:
                known.add(opt_pid)
            profiles = options.get(CONF_PROFILES)
            if isinstance(profiles, Mapping):
                for pid in profiles:
                    if isinstance(pid, str) and pid:
                        known.add(pid)

        for entry in self._async_current_entries() or []:
            _collect(entry)

        if self._existing_entry is not None:
            _collect(self._existing_entry)

        return known

    def _ensure_unique_plant_id(self, plant_id: str) -> str:
        """Return a plant identifier that does not collide with existing profiles."""

        if not isinstance(plant_id, str) or not plant_id:
            return plant_id

        known = {item.casefold() for item in self._known_plant_ids() if isinstance(item, str) and item}

        candidate = plant_id
        base = plant_id
        suffix = 2

        while candidate.casefold() in known:
            candidate = f"{base}_{suffix}"
            suffix += 1

        if candidate != plant_id:
            _LOGGER.warning("Plant identifier '%s' already in use; using fallback '%s' instead", plant_id, candidate)

        return candidate

    def _entry_profile_templates(self) -> dict[str, Mapping[str, Any]]:
        entry = self._existing_entry
        if entry is None:
            entries = self._async_current_entries()
            entry = entries[0] if entries else None

        if entry is None:
            return {}

        raw_profiles = entry.options.get(CONF_PROFILES)
        if not isinstance(raw_profiles, Mapping):
            return {}

        profiles: dict[str, Mapping[str, Any]] = {}
        for plant_id, data in raw_profiles.items():
            if isinstance(plant_id, str) and isinstance(data, Mapping):
                profiles[plant_id] = data
        return profiles

    async def _async_profile_store(self) -> ProfileStore | None:
        if self._profile_store is not None:
            return self._profile_store
        try:
            store = ProfileStore(self.hass)
            await store.async_init()
        except Exception as err:  # pragma: no cover - defensive guard
            _LOGGER.debug("Profile store unavailable: %s", err)
            self._profile_store = None
            return None
        self._profile_store = store
        return store

    async def _async_available_profile_templates(self) -> dict[str, Mapping[str, Any]]:
        if self._profile_templates is not None:
            return self._profile_templates

        templates = self._entry_profile_templates()
        sources: dict[str, str] = dict.fromkeys(templates, "entry")

        store = await self._async_profile_store()
        if store is not None:
            try:
                names = await store.async_list()
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.debug("Unable to list profile library templates: %s", err)
            else:
                try:
                    iterable_names = list(names) if names is not None else []
                except TypeError:
                    iterable_names = []
                except Exception as err:  # pragma: no cover - defensive guard
                    _LOGGER.warning("Unable to iterate profile library templates: %s", err)
                    iterable_names = []

                for name in iterable_names:
                    try:
                        payload = await store.async_get(name)
                    except Exception as err:  # pragma: no cover - defensive guard
                        _LOGGER.warning("Unable to load profile template '%s' from library: %s", name, err)
                        continue
                    if not isinstance(payload, Mapping):
                        continue
                    identifier = (
                        payload.get("plant_id")
                        or payload.get("profile_id")
                        or slugify(payload.get("name"))
                        or slugify(name)
                        or name
                    )
                    key_base = str(identifier)
                    key = key_base
                    suffix = 1
                    while key in templates:
                        suffix += 1
                        key = f"{key_base}_{suffix}"
                    templates[key] = payload
                    sources[key] = "library"

        self._profile_templates = templates
        self._profile_template_sources = sources
        return templates

    def _sensor_notification_id(self) -> str:
        if self._existing_entry is not None:
            return f"horticulture_sensor_{self._existing_entry.entry_id}"
        flow_id = getattr(self, "flow_id", None)
        if isinstance(flow_id, str) and flow_id:
            return f"horticulture_sensor_{flow_id}"
        return "horticulture_sensor_setup"

    def _notify_sensor_warnings(self, issues) -> None:
        if not issues:
            return
        if not _has_registered_service(self.hass, "persistent_notification", "create"):
            _LOGGER.debug("Skipping sensor warning notification; persistent_notification.create not available")
            return
        message = collate_issue_messages(issues)
        notification_id = self._sensor_notification_id()
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Horticulture Assistant sensor warning",
                    "message": message,
                    "notification_id": notification_id,
                },
                blocking=False,
            )
        )

    def _clear_sensor_warning(self) -> None:
        if not _has_registered_service(self.hass, "persistent_notification", "dismiss"):
            return
        notification_id = self._sensor_notification_id()
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": notification_id},
                blocking=False,
            )
        )

    def _apply_threshold_copy(self, profile: Mapping[str, Any]) -> None:
        thresholds = profile.get("thresholds") if isinstance(profile, Mapping) else None
        snapshot: dict[str, Any] = {
            "thresholds": deepcopy(thresholds) if isinstance(thresholds, Mapping) else {},
            "resolved_targets": deepcopy(profile.get("resolved_targets", {}))
            if isinstance(profile.get("resolved_targets"), Mapping)
            else {},
            "variables": deepcopy(profile.get("variables", {}))
            if isinstance(profile.get("variables"), Mapping)
            else {},
        }
        sections = profile.get("sections") if isinstance(profile, Mapping) else None
        if isinstance(sections, Mapping):
            snapshot["sections"] = deepcopy(sections)

        fallback_thresholds = dict(snapshot.get("thresholds", {}))

        try:
            sync_thresholds(snapshot, default_source="manual", prune=False)
        except Exception as err:  # pragma: no cover - exercised via regression test
            identifier = profile.get("plant_id") or profile.get("name") or profile.get("display_name") or "profile"
            _LOGGER.warning(
                "Unable to synchronise copied thresholds for '%s': %s",
                identifier,
                err,
            )
            manual_payload = _build_manual_threshold_payload(fallback_thresholds)
            snapshot = {
                "thresholds": manual_payload["thresholds"],
                "resolved_targets": manual_payload["resolved_targets"],
                "variables": manual_payload["variables"],
            }
            sections_payload = manual_payload.get("sections")
            if isinstance(sections_payload, Mapping):
                snapshot["sections"] = sections_payload
        finally:
            snapshot.setdefault("thresholds", fallback_thresholds)
            snapshot.setdefault("resolved_targets", {})
            snapshot.setdefault("variables", {})

        self._threshold_snapshot = snapshot

        manual_defaults: dict[str, float] = {}
        for key in MANUAL_THRESHOLD_FIELDS:
            value = snapshot["thresholds"].get(key)
            if value in (None, ""):
                continue
            try:
                manual_defaults[key] = float(value)
            except (TypeError, ValueError):
                continue
        self._thresholds = manual_defaults

        general = profile.get("general") if isinstance(profile.get("general"), Mapping) else None

        sensors: Mapping[str, Any] | None = None
        if isinstance(profile.get("sensors"), Mapping):
            sensors = profile["sensors"]  # type: ignore[index]
        elif isinstance(general, Mapping):
            maybe_sensors = general.get("sensors")
            if isinstance(maybe_sensors, Mapping):
                sensors = maybe_sensors

        sensor_defaults: dict[str, str] = {}
        if sensors:
            for option_key, role in SENSOR_OPTION_ROLES.items():
                sensor_value = sensors.get(role)
                if isinstance(sensor_value, str) and sensor_value:
                    sensor_defaults[option_key] = sensor_value
                elif isinstance(sensor_value, list | tuple):
                    first = next((item for item in sensor_value if isinstance(item, str) and item), None)
                    if first:
                        sensor_defaults[option_key] = first
        self._sensor_defaults = sensor_defaults or None

        scope_candidate = _extract_profile_scope(profile) if isinstance(profile, Mapping) else None
        if scope_candidate in PROFILE_SCOPE_CHOICES and self._profile is not None:
            self._profile[CONF_PROFILE_SCOPE] = scope_candidate

        if self._profile is not None and not self._profile.get(CONF_PLANT_TYPE) and isinstance(general, Mapping):
            plant_type = general.get(CONF_PLANT_TYPE)
            if isinstance(plant_type, str) and plant_type:
                self._profile[CONF_PLANT_TYPE] = plant_type

        species_display = profile.get("species_display") if isinstance(profile, Mapping) else None
        if isinstance(species_display, str) and species_display:
            self._species_display = species_display
        elif isinstance(general, Mapping):
            display = general.get("plant_type")
            if isinstance(display, str) and display:
                self._species_display = display

        species_pid = profile.get("species_pid") if isinstance(profile, Mapping) else None
        if isinstance(species_pid, str) and species_pid:
            self._species_pid = species_pid

        image_url = profile.get("image_url") if isinstance(profile, Mapping) else None
        if isinstance(image_url, str) and image_url:
            self._image_url = image_url

        opb_credentials = profile.get("opb_credentials") if isinstance(profile, Mapping) else None
        if isinstance(opb_credentials, Mapping):
            creds: dict[str, str] = {}
            for key, value in opb_credentials.items():
                if isinstance(key, str) and isinstance(value, str):
                    creds[key] = value
            self._opb_credentials = creds or None

    async def async_step_post_setup(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._existing_entry is None:
            return self.async_abort(reason="unknown_profile")

        selector = sel.SelectSelector(
            sel.SelectSelectorConfig(
                options=[
                    {"value": "add_profile", "label": "Add another plant profile"},
                    {"value": "open_options", "label": "Open profile manager"},
                ]
            )
        )
        schema = vol.Schema({vol.Required("next_action", default="add_profile"): selector})

        if user_input is None:
            return self.async_show_form(step_id="post_setup", data_schema=schema)

        action = user_input.get("next_action", "add_profile")
        if action == "open_options":
            return self.async_abort(reason="post_setup_use_options")

        self._config = {}
        self._reset_profile_context()
        return await self.async_step_profile()

    async def async_step_profile(self, user_input=None):
        errors = {}
        defaults: dict[str, Any] = {}
        if self._profile:
            defaults.update(self._profile)
        if user_input is not None and self._config is not None:
            defaults.update(user_input)
            plant_name = user_input[CONF_PLANT_NAME].strip()
            plant_type = user_input.get(CONF_PLANT_TYPE, "").strip()
            profile_scope = user_input.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)
            if profile_scope not in PROFILE_SCOPE_CHOICES:
                profile_scope = PROFILE_SCOPE_DEFAULT
            if not plant_name:
                errors[CONF_PLANT_NAME] = "required"
            else:
                metadata = {CONF_PLANT_NAME: plant_name}
                if plant_type:
                    metadata[CONF_PLANT_TYPE] = plant_type
            plant_id: str | None = None
            generator_error: Exception | None = None
            try:
                plant_id = await self.hass.async_add_executor_job(
                    profile_generator.generate_profile,
                    metadata,
                    self.hass,
                )
            except Exception as err:  # pragma: no cover - unexpected
                generator_error = err
            if not plant_id:
                fallback_id = _derive_fallback_plant_id(plant_name, plant_type)
                if fallback_id:
                    if generator_error is not None:
                        _LOGGER.warning(
                            "Failed to scaffold profile '%s': %s; continuing with fallback identifier '%s'",
                            plant_name,
                            generator_error,
                            fallback_id,
                        )
                    else:
                        _LOGGER.warning(
                            "Profile generator returned no identifier for '%s'; continuing with fallback '%s'",
                            plant_name,
                            fallback_id,
                        )
                    plant_id = fallback_id
                else:
                    message = "Unable to generate profile identifier for '%s'"
                    if generator_error is not None:
                        _LOGGER.warning(message + ": %s", plant_name, generator_error)
                    else:
                        _LOGGER.warning(message, plant_name)
                    errors["base"] = "profile_error"
            if not errors:
                plant_id = self._ensure_unique_plant_id(plant_id)
                self._profile = {
                    CONF_PLANT_ID: plant_id,
                    CONF_PLANT_NAME: plant_name,
                    CONF_PROFILE_SCOPE: profile_scope,
                }
                if plant_type:
                    self._profile[CONF_PLANT_TYPE] = plant_type
                return await self.async_step_threshold_source()

        schema_defaults = {
            CONF_PLANT_NAME: defaults.get(CONF_PLANT_NAME, ""),
            CONF_PLANT_TYPE: defaults.get(CONF_PLANT_TYPE, ""),
            CONF_PROFILE_SCOPE: defaults.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_PLANT_NAME, default=schema_defaults[CONF_PLANT_NAME]): cv.string,
                vol.Optional(CONF_PLANT_TYPE, default=schema_defaults[CONF_PLANT_TYPE]): cv.string,
                vol.Required(
                    CONF_PROFILE_SCOPE,
                    default=schema_defaults[CONF_PROFILE_SCOPE],
                ): sel.SelectSelector(sel.SelectSelectorConfig(options=PROFILE_SCOPE_SELECTOR_OPTIONS)),
            }
        )

        return self.async_show_form(step_id="profile", data_schema=schema, errors=errors)

    async def async_step_threshold_source(self, user_input=None):
        if self._profile is None:
            _LOGGER.debug("Profile metadata missing when selecting threshold source; returning to profile step.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()
        if user_input is not None:
            method = _coerce_threshold_source_method(user_input.get("method")) or "manual"
            if method == "openplantbook":
                self._threshold_snapshot = None
                self._sensor_defaults = None
                return await self.async_step_opb_credentials()
            if method == "skip":
                self._thresholds = {}
                self._threshold_snapshot = None
                self._species_display = None
                self._species_pid = None
                self._image_url = None
                self._sensor_defaults = None
                return await self.async_step_sensors()
            if method == "copy":
                return await self.async_step_threshold_copy()
            self._threshold_snapshot = None
            self._sensor_defaults = None
            return await self.async_step_thresholds()

        templates_available = bool(await self._async_available_profile_templates())

        options = [
            {"value": "openplantbook", "label": "From OpenPlantbook"},
            {"value": "manual", "label": "Manual entry"},
            {"value": "skip", "label": "Skip for now"},
        ]
        if templates_available:
            options.insert(1, {"value": "copy", "label": "Copy an existing profile"})

        schema = vol.Schema(
            {vol.Required("method", default="manual"): sel.SelectSelector(sel.SelectSelectorConfig(options=options))}
        )
        return self.async_show_form(step_id="threshold_source", data_schema=schema)

    async def async_step_threshold_copy(self, user_input=None):
        if self._profile is None:
            _LOGGER.debug("Profile metadata missing when copying thresholds; returning to profile step.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()

        templates = await self._async_available_profile_templates()
        if not templates:
            self._threshold_snapshot = None
            self._sensor_defaults = None
            return await self.async_step_thresholds()

        stored_filter = self._template_filter or ""
        if user_input is not None:
            requested_filter = str(user_input.get("filter") or "").strip()
            if requested_filter != stored_filter:
                self._template_filter = requested_filter
                return await self.async_step_threshold_copy()

        filter_value = self._template_filter or ""
        options: list[tuple[str, str]] = []
        filtered_options: list[tuple[str, str]] = []
        search_terms, source_filters, scope_filters = _parse_template_filter(filter_value)
        text_terms = [term.casefold() for term in search_terms if term]
        filter_active = bool(text_terms or source_filters or scope_filters)

        for plant_id, data in templates.items():
            display_name = None
            for key in ("name", "display_name"):
                value = data.get(key)
                if isinstance(value, str) and value:
                    display_name = value
                    break
            if not display_name:
                display_name = plant_id
            species = data.get("species_display") if isinstance(data.get("species_display"), str) else None
            if not species:
                general = data.get("general") if isinstance(data.get("general"), Mapping) else None
                if isinstance(general, Mapping):
                    species_value = general.get(CONF_PLANT_TYPE)
                    if isinstance(species_value, str) and species_value:
                        species = species_value
            label = f"{display_name} ({species})" if species else display_name
            source = self._profile_template_sources.get(plant_id)
            if source == "library":
                label = f"[Library] {label}"
            options.append((label, plant_id))
            matches = True
            if text_terms:
                label_cf = label.casefold()
                plant_cf = plant_id.casefold()
                species_cf = species.casefold() if species else ""
                matches = all(
                    term in label_cf or term in plant_cf or (species_cf and term in species_cf) for term in text_terms
                )
            if matches and source_filters:
                template_source = _normalize_template_source(self._profile_template_sources.get(plant_id))
                matches = template_source in source_filters
            if matches and scope_filters:
                scope_value = _extract_profile_scope(data)
                matches = scope_value is not None and scope_value in scope_filters
            if matches:
                filtered_options.append((label, plant_id))

        if not options:
            self._threshold_snapshot = None
            self._sensor_defaults = None
            return await self.async_step_thresholds()

        options.sort(key=lambda item: item[0].casefold())
        if filtered_options:
            filtered_options.sort(key=lambda item: item[0].casefold())
        selector_source = filtered_options if filter_active else options
        selector_options = [{"value": pid, "label": label} for label, pid in selector_source]

        schema_fields: dict[Any, Any] = {
            vol.Optional("filter", default=filter_value): str,
        }
        errors: dict[str, str] = {}

        visible_count = len(selector_source)
        total_count = len(options)
        filter_summary = _summarise_template_filters(
            search_terms,
            source_filters,
            scope_filters,
            visible_count,
            total_count,
        )
        placeholders = {"filter_summary": filter_summary}

        if filter_active and not filtered_options:
            errors["base"] = "no_template_matches"
            schema = vol.Schema(schema_fields)
            return self.async_show_form(
                step_id="threshold_copy",
                data_schema=schema,
                errors=errors,
                description_placeholders=placeholders,
            )

        if not selector_options:
            errors["base"] = "no_template_matches"
            schema = vol.Schema(schema_fields)
            return self.async_show_form(
                step_id="threshold_copy",
                data_schema=schema,
                errors=errors,
                description_placeholders=placeholders,
            )

        if user_input is None:
            selector = sel.SelectSelector(sel.SelectSelectorConfig(options=selector_options))
            schema_fields[vol.Required("profile_id", default=selector_options[0]["value"])] = selector
            schema = vol.Schema(schema_fields)
            return self.async_show_form(
                step_id="threshold_copy",
                data_schema=schema,
                errors=errors,
                description_placeholders=placeholders,
            )

        profile_id = user_input.get("profile_id")
        profile = templates.get(profile_id) if isinstance(profile_id, str) else None
        if profile is None:
            return self.async_abort(reason="unknown_profile")

        if self._profile is not None:
            self._apply_threshold_copy(profile)

        self._template_filter = None
        return await self.async_step_thresholds()

    async def async_step_opb_credentials(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                OpenPlantbookClient(self.hass, user_input["client_id"], user_input["secret"])
            except RuntimeError:
                errors["base"] = "opb_missing"
            else:
                self._opb_credentials = {
                    "client_id": user_input["client_id"],
                    "secret": user_input["secret"],
                }
                return await self.async_step_opb_species_search()
        return self.async_show_form(
            step_id="opb_credentials",
            data_schema=vol.Schema(
                {
                    vol.Required("client_id"): str,
                    vol.Required("secret"): str,
                }
            ),
            errors=errors,
        )

    async def async_step_opb_species_search(self, user_input=None):
        if self._opb_credentials is None:
            return self.async_abort(reason="unknown")
        client = OpenPlantbookClient(self.hass, self._opb_credentials["client_id"], self._opb_credentials["secret"])
        if user_input is not None:
            try:
                results = await client.search(user_input["query"])
            except Exception as err:  # pragma: no cover - network issues
                _LOGGER.warning("OpenPlantbook search failed: %s", err)
                return await self.async_step_thresholds()
            if not results:
                return await self.async_step_thresholds()
            self._opb_results = results
            return await self.async_step_opb_species_select()
        schema = vol.Schema({vol.Required("query"): str})
        return self.async_show_form(step_id="opb_species_search", data_schema=schema)

    async def async_step_opb_species_select(self, user_input=None):
        if self._opb_credentials is None:
            return self.async_abort(reason="unknown")
        client = OpenPlantbookClient(self.hass, self._opb_credentials["client_id"], self._opb_credentials["secret"])
        results = self._opb_results
        if user_input is not None:
            pid = user_input["pid"]
            try:
                detail = await client.get_details(pid)
            except Exception as err:  # pragma: no cover - network issues
                _LOGGER.warning("OpenPlantbook details failed: %s", err)
                return await self.async_step_thresholds()
            self._species_pid = pid
            self._species_display = next((r["display"] for r in results if r["pid"] == pid), pid)
            thresholds = {
                "temperature_min": detail.get("min_temp"),
                "temperature_max": detail.get("max_temp"),
                "humidity_min": detail.get("min_hum"),
                "humidity_max": detail.get("max_hum"),
                "illuminance_min": detail.get("min_lux"),
                "illuminance_max": detail.get("max_lux"),
                "conductivity_min": detail.get("min_soil_ec"),
                "conductivity_max": detail.get("max_soil_ec"),
            }
            self._thresholds = {k: v for k, v in thresholds.items() if v is not None}
            image_url = detail.get("image_url") or detail.get("image")
            self._image_url = image_url
            if image_url:
                auto_dl = True
                dl_path = Path(self.hass.config.path("www/images/plants"))
                existing = self._async_current_entries()
                if existing:
                    opts = existing[0].options
                    auto_dl = opts.get("opb_auto_download_images", True)
                    dl_path = Path(opts.get("opb_download_dir", dl_path))
                if auto_dl:
                    name = self._profile.get(CONF_PLANT_NAME, "") if self._profile else ""
                    local_url = await client.download_image(name, image_url, dl_path)
                    if local_url:
                        self._image_url = local_url
            return await self.async_step_thresholds()
        schema = vol.Schema(
            {
                vol.Required("pid"): sel.SelectSelector(
                    sel.SelectSelectorConfig(options=[{"value": r["pid"], "label": r["display"]} for r in results])
                )
            }
        )
        return self.async_show_form(step_id="opb_species_select", data_schema=schema)

    async def async_step_thresholds(self, user_input=None):
        if self._profile is None:
            _LOGGER.debug("Profile metadata missing at thresholds step; returning to profile form.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()

        defaults = self._thresholds
        schema_fields: dict[Any, Any] = {}
        for key in MANUAL_THRESHOLD_FIELDS:
            default = defaults.get(key)
            option = vol.Optional(key, default=str(default) if default is not None else "")
            schema_fields[option] = vol.Any(str, int, float)
        schema = vol.Schema(schema_fields, extra=vol.ALLOW_EXTRA)

        if user_input is not None:
            errors: dict[str, str] = {}
            cleaned: dict[str, float] = {}
            for key in MANUAL_THRESHOLD_FIELDS:
                raw = user_input.get(key)
                if raw in (None, "", []):
                    continue
                try:
                    cleaned[key] = float(raw)
                except (TypeError, ValueError):
                    errors[key] = "invalid_float"
            if errors:
                return self.async_show_form(step_id="thresholds", data_schema=schema, errors=errors)

            try:
                violations = evaluate_threshold_bounds(cleaned)
            except Exception as err:  # pragma: no cover - defensive fallback
                plant_reference = self._profile.get(CONF_PLANT_ID) or self._profile.get(CONF_PLANT_NAME) or "<unknown>"
                _LOGGER.exception("Unable to validate manual thresholds for '%s': %s", plant_reference, err)
                violations = []
            if violations:
                error_summary = [violation.message() for violation in violations[:3]]
                if len(violations) > 3:
                    error_summary.append(f"(+{len(violations) - 3} more)")
                placeholders = {"issue_detail": "\n".join(error_summary)}
                field_errors = {issue.key: "threshold_field_error" for issue in violations}
                field_errors["base"] = "threshold_out_of_bounds"
                return self.async_show_form(
                    step_id="thresholds",
                    data_schema=schema,
                    errors=field_errors,
                    description_placeholders=placeholders,
                )
            self._thresholds = cleaned
            return await self.async_step_sensors()

        return self.async_show_form(step_id="thresholds", data_schema=schema)

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if self._profile is None:
            _LOGGER.debug("Profile metadata missing at sensors step; returning to profile form.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()

        schema, placeholders = _build_sensor_schema(self.hass, self._sensor_defaults)
        plant_id = self._profile.get(CONF_PLANT_ID, "<unknown>")

        errors = {}
        if user_input is not None:
            cleaned_input = dict(user_input)
            normalised_values: dict[str, str] = {}
            for key in (
                CONF_MOISTURE_SENSOR,
                CONF_TEMPERATURE_SENSOR,
                CONF_EC_SENSOR,
                CONF_CO2_SENSOR,
            ):
                try:
                    entity_id = _select_sensor_value(user_input.get(key))
                except Exception as err:  # pragma: no cover - defensive guard
                    _LOGGER.warning(
                        "Unable to normalise sensor input for '%s' while completing profile '%s': %s",
                        key,
                        plant_id,
                        err,
                    )
                    cleaned_input.pop(key, None)
                    errors[key] = "invalid_sensor"
                    continue
                if entity_id is None:
                    cleaned_input.pop(key, None)
                    continue
                cleaned_input[key] = entity_id
                normalised_values[key] = entity_id
                if entity_id and self.hass.states.get(entity_id) is None:
                    errors[key] = "not_found"
            if errors:
                return self.async_show_form(
                    step_id="sensors", data_schema=schema, errors=errors, description_placeholders=placeholders
                )
            sensor_map = {SENSOR_OPTION_ROLES[key]: entity_id for key, entity_id in normalised_values.items()}
            if sensor_map:
                try:
                    validation = validate_sensor_links(self.hass, sensor_map)
                except Exception as err:  # pragma: no cover - defensive guard
                    _LOGGER.warning("Unable to validate sensors for '%s': %s", plant_id, err)
                    self._clear_sensor_warning()
                else:
                    issues = _coerce_validation_items(validation, "errors")
                    for issue in issues:
                        role = _issue_role(issue)
                        if not role:
                            continue
                        option_key = next(
                            (opt for opt, mapped_role in SENSOR_OPTION_ROLES.items() if mapped_role == role),
                            None,
                        )
                        if not option_key or option_key in errors:
                            continue
                        errors[option_key] = _issue_code(issue)
                    warnings = _coerce_validation_items(validation, "warnings")
                    filtered_warnings = _filter_sensor_warning_payload(warnings)
                    if filtered_warnings:
                        self._notify_sensor_warnings(filtered_warnings)
                    else:
                        if warnings:
                            _LOGGER.debug(
                                "Dropping sensor warning payload due to unexpected structure: %s",
                                warnings,
                            )
                        self._clear_sensor_warning()
            else:
                self._clear_sensor_warning()
            if errors:
                return self.async_show_form(
                    step_id="sensors", data_schema=schema, errors=errors, description_placeholders=placeholders
                )
            return await self._complete_profile(cleaned_input)

        return self.async_show_form(step_id="sensors", data_schema=schema, description_placeholders=placeholders)

    async def _complete_profile(self, user_input: dict[str, Any]) -> FlowResult:
        if self._profile is None:
            _LOGGER.debug("Attempted to complete profile without metadata; restarting profile step.")
            if self._config is None:
                self._config = {}
            return await self.async_step_profile()

        plant_id = self._profile[CONF_PLANT_ID]
        profile_name = self._profile[CONF_PLANT_NAME]
        profile_scope = self._profile.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)
        plant_type = self._profile.get(CONF_PLANT_TYPE)
        general_path = self.hass.config.path("plants", plant_id, "general.json")
        cleaned_input = dict(user_input)

        try:

            def _sensor_entry(option_key: str) -> str | None:
                try:
                    value = _select_sensor_value(user_input.get(option_key))
                except Exception as err:  # pragma: no cover - defensive guard
                    _LOGGER.warning(
                        "Unable to finalise sensor '%s' for '%s': %s",
                        option_key,
                        plant_id,
                        err,
                    )
                    cleaned_input.pop(option_key, None)
                    return None
                if value is None:
                    cleaned_input.pop(option_key, None)
                    return None
                cleaned_input[option_key] = value
                return value

            sensor_map: dict[str, list[str]] = {}
            if moisture := _sensor_entry(CONF_MOISTURE_SENSOR):
                sensor_map["moisture_sensors"] = [moisture]
            if temperature := _sensor_entry(CONF_TEMPERATURE_SENSOR):
                sensor_map["temperature_sensors"] = [temperature]
            if ec := _sensor_entry(CONF_EC_SENSOR):
                sensor_map["ec_sensors"] = [ec]
            if co2 := _sensor_entry(CONF_CO2_SENSOR):
                sensor_map["co2_sensors"] = [co2]

            try:
                await self.hass.async_add_executor_job(
                    _ensure_general_profile_file,
                    general_path,
                    plant_id,
                    profile_name,
                    plant_type,
                    profile_scope,
                    sensor_map if sensor_map else None,
                )
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.warning("Unable to persist profile metadata for '%s': %s", plant_id, err)
            try:
                await self.hass.async_add_executor_job(
                    register_plant,
                    plant_id,
                    {
                        "display_name": profile_name,
                        "profile_path": f"plants/{plant_id}/general.json",
                        **({"plant_type": plant_type} if plant_type else {}),
                    },
                    self.hass,
                )
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.warning("Unable to register plant '%s': %s", plant_id, err)
            mapped: dict[str, str] = {}
            if moisture:
                mapped["moisture"] = moisture
            if temperature := cleaned_input.get(CONF_TEMPERATURE_SENSOR):
                mapped["temperature"] = temperature
            if ec := cleaned_input.get(CONF_EC_SENSOR):
                mapped["conductivity"] = ec
            if co2 := cleaned_input.get(CONF_CO2_SENSOR):
                mapped["co2"] = co2

            if not mapped and self._sensor_defaults:
                for option_key, role in SENSOR_OPTION_ROLES.items():
                    default_value = self._sensor_defaults.get(option_key) if self._sensor_defaults else None
                    if isinstance(default_value, str) and default_value:
                        mapped[role] = default_value

            general_section: dict[str, Any] = {"display_name": profile_name}
            if mapped:
                general_section["sensors"] = dict(mapped)
            if plant_type:
                general_section.setdefault("plant_type", plant_type)
            general_section.setdefault(CONF_PROFILE_SCOPE, profile_scope)

            sync_kwargs: dict[str, Any] = {"default_source": "manual"}
            if self._threshold_snapshot is not None:
                thresholds_payload = deepcopy(self._threshold_snapshot)
                thresholds_section = thresholds_payload.setdefault("thresholds", {})
                thresholds_section.update(self._thresholds)
                touched_keys = list(self._thresholds)
                if touched_keys:
                    sync_kwargs["touched_keys"] = touched_keys
                sync_kwargs["prune"] = False
            else:
                thresholds_payload = {"thresholds": dict(self._thresholds)}

            fallback_thresholds = dict(thresholds_payload.get("thresholds", {}))

            try:
                sync_thresholds(thresholds_payload, **sync_kwargs)
            except Exception as err:  # pragma: no cover - defensive guard
                _LOGGER.warning("Unable to synchronise profile thresholds for '%s': %s", plant_id, err)
                thresholds_payload = _build_manual_threshold_payload(fallback_thresholds)

            thresholds_payload.setdefault("thresholds", fallback_thresholds)
            thresholds_payload.setdefault("resolved_targets", {})
            thresholds_payload.setdefault("variables", {})

            profile_entry: dict[str, Any] = {
                "name": profile_name,
                "plant_id": plant_id,
                "sensors": dict(mapped),
                "thresholds": thresholds_payload["thresholds"],
                "resolved_targets": thresholds_payload["resolved_targets"],
                "variables": thresholds_payload["variables"],
            }
            profile_entry[CONF_PROFILE_SCOPE] = profile_scope
            if general_section:
                profile_entry["general"] = general_section
            if sections := thresholds_payload.get("sections"):
                profile_entry["sections"] = sections
            if self._species_display:
                profile_entry["species_display"] = self._species_display
            if self._species_pid:
                profile_entry["species_pid"] = self._species_pid
            if self._image_url:
                profile_entry["image_url"] = self._image_url
            if self._opb_credentials:
                profile_entry["opb_credentials"] = self._opb_credentials

            try:
                ensure_sections(profile_entry, plant_id=plant_id, display_name=profile_name)
            except Exception as err:
                _LOGGER.warning("Unable to normalise profile sections for '%s': %s", plant_id, err)
                fallback_sections = dict(profile_entry.get("sections") or {})
                fallback_sections.setdefault("library", {})
                fallback_sections.setdefault("local", {})
                profile_entry["sections"] = fallback_sections
                profile_entry.setdefault("library", {})
                profile_entry.setdefault("local", {})

                fallback_general = dict(profile_entry.get("general") or {})
                if mapped:
                    fallback_general.setdefault("sensors", dict(mapped))
                if plant_type:
                    fallback_general.setdefault(CONF_PLANT_TYPE, plant_type)
                fallback_general.setdefault(CONF_PROFILE_SCOPE, profile_scope)
                fallback_general.setdefault("display_name", profile_name)
                profile_entry["general"] = fallback_general
                profile_entry.setdefault("display_name", profile_name)

            data = {**(self._config or {}), **self._profile}
            if self._existing_entry is not None:
                await self._async_store_profile_for_existing_entry(
                    plant_id,
                    profile_entry,
                )
                return self.async_abort(
                    reason="profile_added",
                    description_placeholders={"profile": profile_name},
                )

            options = dict(cleaned_input)
            options["sensors"] = dict(mapped)
            options["thresholds"] = thresholds_payload["thresholds"]
            options["resolved_targets"] = thresholds_payload["resolved_targets"]
            options["variables"] = thresholds_payload["variables"]
            options[CONF_PROFILES] = {plant_id: profile_entry}
            if self._species_display:
                options["species_display"] = self._species_display
            if self._species_pid:
                options["species_pid"] = self._species_pid
            if self._image_url:
                options["image_url"] = self._image_url
            if self._opb_credentials:
                options["opb_credentials"] = self._opb_credentials
            return self.async_create_entry(title=profile_name, data=data, options=options)
        except Exception:  # pragma: no cover - defensive guard
            _LOGGER.exception(
                "Profile completion for '%s' failed; storing manual fallback.",
                plant_id,
            )
            return await self._async_profile_completion_fallback(
                plant_id,
                profile_name,
                profile_scope,
                plant_type,
                general_path,
                cleaned_input,
            )

    async def _async_profile_completion_fallback(
        self,
        plant_id: str,
        profile_name: str,
        profile_scope: str,
        plant_type: str | None,
        general_path: str,
        user_input: dict[str, Any],
    ) -> FlowResult:
        def _coerce_sensor(option_key: str) -> str | None:
            value = user_input.get(option_key)
            if isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    return candidate
            return None

        mapped: dict[str, str] = {}
        cleaned: dict[str, Any] = dict(user_input)
        sensor_map: dict[str, list[str]] = {}
        for option_key, role in SENSOR_OPTION_ROLES.items():
            entity_id = _coerce_sensor(option_key)
            if not entity_id:
                cleaned.pop(option_key, None)
                continue
            cleaned[option_key] = entity_id
            mapped[role] = entity_id
            sensor_map[f"{role}_sensors"] = [entity_id]

        if not mapped and self._sensor_defaults:
            for option_key, role in SENSOR_OPTION_ROLES.items():
                default_value = self._sensor_defaults.get(option_key) if self._sensor_defaults else None
                if isinstance(default_value, str) and default_value:
                    mapped[role] = default_value

        general_section: dict[str, Any] = {"display_name": profile_name, CONF_PROFILE_SCOPE: profile_scope}
        if plant_type:
            general_section.setdefault(CONF_PLANT_TYPE, plant_type)
        if mapped:
            general_section["sensors"] = dict(mapped)

        try:
            await self.hass.async_add_executor_job(
                _ensure_general_profile_file,
                general_path,
                plant_id,
                profile_name,
                plant_type,
                profile_scope,
                sensor_map if sensor_map else None,
            )
        except Exception as general_err:  # pragma: no cover - defensive guard
            _LOGGER.debug("Unable to persist fallback metadata for '%s': %s", plant_id, general_err)

        base_thresholds: dict[str, Any] = {}
        if self._threshold_snapshot is not None:
            base_thresholds.update(self._threshold_snapshot.get("thresholds", {}))
        base_thresholds.update(self._thresholds)
        thresholds_payload = _build_manual_threshold_payload(base_thresholds)

        profile_entry: dict[str, Any] = {
            "name": profile_name,
            "plant_id": plant_id,
            "sensors": dict(mapped),
            "thresholds": thresholds_payload["thresholds"],
            "resolved_targets": thresholds_payload["resolved_targets"],
            "variables": thresholds_payload["variables"],
            CONF_PROFILE_SCOPE: profile_scope,
        }
        profile_entry["general"] = general_section
        profile_entry["sections"] = thresholds_payload.get("sections", {})
        if self._species_display:
            profile_entry["species_display"] = self._species_display
        if self._species_pid:
            profile_entry["species_pid"] = self._species_pid
        if self._image_url:
            profile_entry["image_url"] = self._image_url
        if self._opb_credentials:
            profile_entry["opb_credentials"] = self._opb_credentials

        data = {**(self._config or {}), **self._profile}
        if self._existing_entry is not None:
            await self._async_store_profile_for_existing_entry(plant_id, profile_entry)
            return self.async_abort(
                reason="profile_added",
                description_placeholders={"profile": profile_name},
            )

        options = dict(cleaned)
        options["sensors"] = dict(mapped)
        options["thresholds"] = thresholds_payload["thresholds"]
        options["resolved_targets"] = thresholds_payload["resolved_targets"]
        options["variables"] = thresholds_payload["variables"]
        options[CONF_PROFILES] = {plant_id: profile_entry}
        if self._species_display:
            options["species_display"] = self._species_display
        if self._species_pid:
            options["species_pid"] = self._species_pid
        if self._image_url:
            options["image_url"] = self._image_url
        if self._opb_credentials:
            options["opb_credentials"] = self._opb_credentials

        return self.async_create_entry(title=profile_name, data=data, options=options)

    async def _async_store_profile_for_existing_entry(
        self,
        plant_id: str,
        profile_entry: dict[str, Any],
    ) -> None:
        entry = self._existing_entry
        if entry is None:
            return

        options = dict(entry.options)
        profiles = dict(options.get(CONF_PROFILES, {}))
        profiles[plant_id] = profile_entry
        options[CONF_PROFILES] = profiles

        self.hass.config_entries.async_update_entry(entry, options=options)

    @staticmethod
    def async_get_options_flow(config_entry):
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self.config_entry = entry
        self._pid: str | None = None
        self._var: str | None = None
        self._mode: str | None = None
        self._cal_session: str | None = None
        self._new_profile_id: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "basic",
                "cloud_sync",
                "add_profile",
                "manage_profiles",
                "configure_ai",
                "profile_targets",
                "nutrient_schedule",
            ],
        )

    async def _async_get_registry(self):
        from .profile_registry import ProfileRegistry

        domain_data = self.hass.data.setdefault(DOMAIN, {})
        registry: ProfileRegistry | None = domain_data.get("registry")
        if registry is None:
            registry = ProfileRegistry(self.hass, self._entry)
            await registry.async_initialize()
            domain_data["registry"] = registry
        return registry

    def _notify_sensor_warnings(self, issues) -> None:
        if not issues:
            return
        if not _has_registered_service(self.hass, "persistent_notification", "create"):
            _LOGGER.debug("Skipping sensor warning notification; persistent_notification.create not available")
            return
        message = collate_issue_messages(issues)
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Horticulture Assistant sensor warning",
                    "message": message,
                    "notification_id": f"horticulture_sensor_{self._entry.entry_id}",
                },
                blocking=False,
            )
        )

    def _clear_sensor_warning(self) -> None:
        if not _has_registered_service(self.hass, "persistent_notification", "dismiss"):
            return
        self.hass.async_create_task(
            self.hass.services.async_call(
                "persistent_notification",
                "dismiss",
                {"notification_id": f"horticulture_sensor_{self._entry.entry_id}"},
                blocking=False,
            )
        )

    async def async_step_basic(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        defaults = {
            CONF_MODEL: self._entry.options.get(
                CONF_MODEL,
                self._entry.data.get(CONF_MODEL, DEFAULT_MODEL),
            ),
            CONF_BASE_URL: self._entry.options.get(
                CONF_BASE_URL,
                self._entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            ),
            CONF_UPDATE_INTERVAL: self._entry.options.get(
                CONF_UPDATE_INTERVAL,
                self._entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
            ),
            CONF_KEEP_STALE: self._entry.options.get(
                CONF_KEEP_STALE,
                self._entry.data.get(CONF_KEEP_STALE, DEFAULT_KEEP_STALE),
            ),
            "species_display": self._entry.options.get(
                "species_display",
                self._entry.data.get(CONF_PLANT_TYPE, ""),
            ),
            CONF_MOISTURE_SENSOR: self._entry.options.get(CONF_MOISTURE_SENSOR, ""),
            CONF_TEMPERATURE_SENSOR: self._entry.options.get(CONF_TEMPERATURE_SENSOR, ""),
            CONF_EC_SENSOR: self._entry.options.get(CONF_EC_SENSOR, ""),
            CONF_CO2_SENSOR: self._entry.options.get(CONF_CO2_SENSOR, ""),
            "opb_auto_download_images": self._entry.options.get("opb_auto_download_images", True),
            "opb_download_dir": self._entry.options.get(
                "opb_download_dir",
                self.hass.config.path("www/images/plants"),
            ),
            "opb_location_share": self._entry.options.get("opb_location_share", "off"),
            "opb_enable_upload": self._entry.options.get("opb_enable_upload", False),
        }

        sensor_defaults = {
            CONF_MOISTURE_SENSOR: defaults[CONF_MOISTURE_SENSOR],
            CONF_TEMPERATURE_SENSOR: defaults[CONF_TEMPERATURE_SENSOR],
            CONF_EC_SENSOR: defaults[CONF_EC_SENSOR],
            CONF_CO2_SENSOR: defaults[CONF_CO2_SENSOR],
        }
        sensor_schema, placeholders = _build_sensor_schema(self.hass, sensor_defaults)

        schema_fields: dict[Any, Any] = {
            vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
            vol.Optional(CONF_BASE_URL, default=defaults[CONF_BASE_URL]): str,
            vol.Optional(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): int,
            vol.Optional(CONF_KEEP_STALE, default=defaults[CONF_KEEP_STALE]): bool,
            vol.Optional("species_display", default=defaults["species_display"]): str,
            vol.Optional(
                "opb_auto_download_images",
                default=defaults["opb_auto_download_images"],
            ): bool,
            vol.Optional("opb_download_dir", default=defaults["opb_download_dir"]): str,
            vol.Optional(
                "opb_location_share",
                default=defaults["opb_location_share"],
            ): sel.SelectSelector(
                sel.SelectSelectorConfig(
                    options=[
                        {"value": "off", "label": "off"},
                        {"value": "country", "label": "country"},
                        {"value": "coordinates", "label": "coordinates"},
                    ]
                )
            ),
            vol.Optional("opb_enable_upload", default=defaults["opb_enable_upload"]): bool,
            vol.Optional("force_refresh", default=False): bool,
        }
        schema_fields.update(sensor_schema.schema)
        schema = vol.Schema(schema_fields)

        errors = {}
        if user_input is not None:
            interval_candidate = user_input.get(CONF_UPDATE_INTERVAL)
            if interval_candidate is not None:
                try:
                    interval_value = int(interval_candidate)
                except (TypeError, ValueError):
                    errors[CONF_UPDATE_INTERVAL] = "invalid_interval"
                else:
                    if interval_value < 1:
                        errors[CONF_UPDATE_INTERVAL] = "invalid_interval"
                    else:
                        user_input[CONF_UPDATE_INTERVAL] = interval_value
            if errors:
                return self.async_show_form(
                    step_id="basic",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders=placeholders,
                )
            for key in (
                CONF_MOISTURE_SENSOR,
                CONF_TEMPERATURE_SENSOR,
                CONF_EC_SENSOR,
                CONF_CO2_SENSOR,
            ):
                entity_id = user_input.get(key)
                if entity_id and self.hass.states.get(entity_id) is None:
                    errors[key] = "not_found"
            sensor_map = {
                SENSOR_OPTION_ROLES[key]: user_input[key] for key in SENSOR_OPTION_ROLES if user_input.get(key)
            }
            if sensor_map:
                identifier = (
                    self._entry.data.get(CONF_PLANT_ID) or self._entry.title or self._entry.entry_id or "<unknown>"
                )
                try:
                    validation = validate_sensor_links(self.hass, sensor_map)
                except Exception as err:  # pragma: no cover - defensive guard
                    _LOGGER.warning("Unable to validate sensors for '%s': %s", identifier, err)
                    self._clear_sensor_warning()
                else:
                    for issue in validation.errors:
                        option_key = next(
                            (opt for opt, role in SENSOR_OPTION_ROLES.items() if role == issue.role),
                            None,
                        )
                        if option_key and option_key not in errors:
                            errors[option_key] = issue.issue
                    if validation.warnings:
                        self._notify_sensor_warnings(validation.warnings)
                    else:
                        self._clear_sensor_warning()
            else:
                self._clear_sensor_warning()
            if errors:
                return self.async_show_form(
                    step_id="basic",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders=placeholders,
                )
            sensor_map: dict[str, list[str]] = {}
            if moisture := user_input.get(CONF_MOISTURE_SENSOR):
                sensor_map["moisture_sensors"] = [moisture]
            if temperature := user_input.get(CONF_TEMPERATURE_SENSOR):
                sensor_map["temperature_sensors"] = [temperature]
            if ec := user_input.get(CONF_EC_SENSOR):
                sensor_map["ec_sensors"] = [ec]
            if co2 := user_input.get(CONF_CO2_SENSOR):
                sensor_map["co2_sensors"] = [co2]

            plant_id = self._entry.data.get(CONF_PLANT_ID)
            if plant_id:

                def _save_sensors():
                    path = self.hass.config.path("plants", plant_id, "general.json")
                    try:
                        data = load_json(path)
                    except Exception:
                        data = {}
                    container = data.setdefault("sensor_entities", {})
                    for key in (
                        "moisture_sensors",
                        "temperature_sensors",
                        "ec_sensors",
                        "co2_sensors",
                    ):
                        if key in sensor_map:
                            container[key] = sensor_map[key]
                        else:
                            container.pop(key, None)
                    if not container:
                        data.pop("sensor_entities", None)
                    save_json(path, data)

                await self.hass.async_add_executor_job(_save_sensors)

            opts = dict(self._entry.options)
            mapped = {}
            for key, role in (
                (CONF_MOISTURE_SENSOR, "moisture"),
                (CONF_TEMPERATURE_SENSOR, "temperature"),
                (CONF_EC_SENSOR, "conductivity"),
                (CONF_CO2_SENSOR, "co2"),
            ):
                if key in user_input:
                    value = user_input.get(key)
                    if value:
                        opts[key] = value
                        mapped[role] = value
                    else:
                        opts.pop(key, None)
                else:
                    opts.pop(key, None)
            opts["sensors"] = mapped
            profiles = dict(opts.get(CONF_PROFILES, {}))
            plant_id = self._entry.data.get(CONF_PLANT_ID)
            if plant_id:
                primary = dict(profiles.get(plant_id, {}))
                name = primary.get("name") or self._entry.title or opts.get(CONF_PLANT_NAME) or plant_id
                primary["name"] = name
                primary["plant_id"] = plant_id
                if mapped:
                    primary["sensors"] = dict(mapped)
                else:
                    primary.pop("sensors", None)
                general = dict(primary.get("general", {}))
                if mapped:
                    general["sensors"] = dict(mapped)
                else:
                    general.pop("sensors", None)
                general.setdefault(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)
                species_value = (
                    opts.get("species_display")
                    or self._entry.options.get("species_display")
                    or self._entry.data.get(CONF_PLANT_TYPE)
                )
                if species_value and "plant_type" not in general:
                    general["plant_type"] = species_value
                if general:
                    primary["general"] = general
                elif "general" in primary:
                    primary.pop("general")
                ensure_sections(primary, plant_id=plant_id, display_name=name)
                profiles[plant_id] = primary
                opts[CONF_PROFILES] = profiles
            if "species_display" in user_input:
                value = user_input.get("species_display")
                if value:
                    opts["species_display"] = value
                else:
                    opts.pop("species_display", None)
            opts.update(
                {
                    k: v
                    for k, v in user_input.items()
                    if k
                    not in (
                        CONF_MOISTURE_SENSOR,
                        CONF_TEMPERATURE_SENSOR,
                        CONF_EC_SENSOR,
                        CONF_CO2_SENSOR,
                        "force_refresh",
                        "species_display",
                    )
                }
            )
            if user_input.get("force_refresh"):
                plant_id = self._entry.data.get(CONF_PLANT_ID)
                plant_name = self._entry.data.get(CONF_PLANT_NAME)
                if plant_id and plant_name:
                    metadata = {
                        CONF_PLANT_ID: plant_id,
                        CONF_PLANT_NAME: plant_name,
                    }
                    if species := opts.get("species_display"):
                        metadata[CONF_PLANT_TYPE] = species
                    await self.hass.async_add_executor_job(
                        profile_generator.generate_profile,
                        metadata,
                        self.hass,
                        True,
                    )
            return self.async_create_entry(title="", data=opts)

        return self.async_show_form(
            step_id="basic",
            data_schema=schema,
            description_placeholders=placeholders,
        )

    async def async_step_profile_targets(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        self._pid = None
        self._var = None
        return await self.async_step_profile(user_input)

    async def async_step_nutrient_schedule(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        profiles = self._profiles()
        if not profiles:
            return self.async_abort(reason="no_profiles")
        if user_input is None or "profile_id" not in user_input:
            return self.async_show_form(
                step_id="nutrient_schedule",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile_id"): vol.In({pid: data["name"] for pid, data in profiles.items()}),
                    }
                ),
            )
        self._pid = user_input["profile_id"]
        return await self.async_step_nutrient_schedule_edit()

    async def async_step_nutrient_schedule_edit(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if not self._pid:
            return await self.async_step_nutrient_schedule()
        profiles = self._profiles()
        profile = profiles.get(self._pid)
        if profile is None:
            return self.async_abort(reason="unknown_profile")

        existing = self._extract_nutrient_schedule(profile)
        schedule_text = json.dumps(existing, indent=2, ensure_ascii=False) if existing else ""

        schema = vol.Schema(
            {
                vol.Optional("auto_generate", default=False): bool,
                vol.Optional(
                    "schedule",
                    default=schedule_text,
                ): sel.TextSelector(sel.TextSelectorConfig(type="text", multiline=True)),
            }
        )

        errors: dict[str, str] = {}
        description_placeholders = {
            "profile": profile.get("name") or profile.get("display_name") or self._pid,
            "current_count": str(len(existing)),
            "example": json.dumps(
                [
                    {
                        "stage": "vegetative",
                        "duration_days": 14,
                        "totals_mg": {"N": 850.0, "K": 630.0},
                    },
                    {
                        "stage": "flowering",
                        "duration_days": 21,
                        "totals_mg": {"N": 600.0, "P": 420.0, "K": 900.0},
                    },
                ],
                indent=2,
                ensure_ascii=False,
            ),
        }
        try:
            plant_type = self._infer_nutrient_schedule_plant_type(profile)
        except Exception:  # pragma: no cover - defensive guard
            plant_type = None
        description_placeholders["plant_type"] = plant_type or "unknown"

        if user_input is not None:
            schedule_payload: list[dict[str, Any]] | None = None
            if user_input.get("auto_generate"):
                try:
                    schedule_payload = self._generate_schedule_for_profile(profile)
                except Exception:  # pragma: no cover - generation failures are logged via UI
                    errors["auto_generate"] = "generation_failed"
            else:
                raw_text = user_input.get("schedule", "").strip()
                if raw_text:
                    try:
                        loaded = json.loads(raw_text)
                    except json.JSONDecodeError:
                        errors["schedule"] = "invalid_json"
                    else:
                        if isinstance(loaded, list):
                            try:
                                schedule_payload = [self._coerce_schedule_row(item) for item in loaded]
                            except ValueError:
                                errors["schedule"] = "invalid_row"
                        else:
                            errors["schedule"] = "invalid_format"
                else:
                    schedule_payload = []
            if not errors and schedule_payload is not None:
                self._apply_nutrient_schedule(self._pid, schedule_payload)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="nutrient_schedule_edit",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_cloud_sync(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        defaults = {
            CONF_CLOUD_SYNC_ENABLED: bool(self._entry.options.get(CONF_CLOUD_SYNC_ENABLED, False)),
            CONF_CLOUD_BASE_URL: self._entry.options.get(CONF_CLOUD_BASE_URL, ""),
            CONF_CLOUD_TENANT_ID: self._entry.options.get(CONF_CLOUD_TENANT_ID, ""),
            CONF_CLOUD_DEVICE_TOKEN: self._entry.options.get(CONF_CLOUD_DEVICE_TOKEN, ""),
            CONF_CLOUD_SYNC_INTERVAL: self._entry.options.get(CONF_CLOUD_SYNC_INTERVAL, DEFAULT_CLOUD_SYNC_INTERVAL),
        }

        schema = vol.Schema(
            {
                vol.Required(CONF_CLOUD_SYNC_ENABLED, default=defaults[CONF_CLOUD_SYNC_ENABLED]): bool,
                vol.Optional(CONF_CLOUD_BASE_URL, default=defaults[CONF_CLOUD_BASE_URL]): str,
                vol.Optional(CONF_CLOUD_TENANT_ID, default=defaults[CONF_CLOUD_TENANT_ID]): str,
                vol.Optional(CONF_CLOUD_DEVICE_TOKEN, default=defaults[CONF_CLOUD_DEVICE_TOKEN]): str,
                vol.Optional(CONF_CLOUD_SYNC_INTERVAL, default=defaults[CONF_CLOUD_SYNC_INTERVAL]): int,
            }
        )

        if user_input is not None:
            opts = dict(self._entry.options)
            enabled = bool(user_input.get(CONF_CLOUD_SYNC_ENABLED, False))
            opts[CONF_CLOUD_SYNC_ENABLED] = enabled

            base_url = str(user_input.get(CONF_CLOUD_BASE_URL, "")).strip()
            tenant_id = str(user_input.get(CONF_CLOUD_TENANT_ID, "")).strip()
            device_token = str(user_input.get(CONF_CLOUD_DEVICE_TOKEN, "")).strip()

            if base_url:
                opts[CONF_CLOUD_BASE_URL] = base_url
            else:
                opts.pop(CONF_CLOUD_BASE_URL, None)

            if tenant_id:
                opts[CONF_CLOUD_TENANT_ID] = tenant_id
            else:
                opts.pop(CONF_CLOUD_TENANT_ID, None)

            if enabled and device_token:
                opts[CONF_CLOUD_DEVICE_TOKEN] = device_token
            else:
                opts.pop(CONF_CLOUD_DEVICE_TOKEN, None)

            interval_value = user_input.get(CONF_CLOUD_SYNC_INTERVAL)
            try:
                interval = max(15, int(interval_value)) if interval_value is not None else None
            except (TypeError, ValueError):
                interval = DEFAULT_CLOUD_SYNC_INTERVAL
            if interval is not None:
                opts[CONF_CLOUD_SYNC_INTERVAL] = interval
            else:
                opts.pop(CONF_CLOUD_SYNC_INTERVAL, None)

            return self.async_create_entry(title="", data=opts)

        return self.async_show_form(step_id="cloud_sync", data_schema=schema)

    async def async_step_add_profile(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        registry = await self._async_get_registry()

        if user_input is not None:
            scope = user_input.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT)
            copy_from = user_input.get("copy_from")
            pid = await registry.async_add_profile(user_input["name"], copy_from, scope=scope)

            entry_records = get_entry_data(self.hass, self._entry) or {}
            store = entry_records.get("profile_store") if isinstance(entry_records, Mapping) else None
            if store is not None:
                new_profile = registry.get_profile(pid)
                if new_profile is not None:
                    profile_json = new_profile.to_json()
                    sensors = profile_json.get("general", {}).get("sensors", {})
                    clone_payload = deepcopy(profile_json)
                    general = clone_payload.setdefault("general", {})
                    if isinstance(sensors, dict):
                        general.setdefault("sensors", dict(sensors))
                        clone_payload["sensors"] = dict(sensors)
                    if scope is not None:
                        general[CONF_PROFILE_SCOPE] = scope
                    elif CONF_PROFILE_SCOPE not in general:
                        general[CONF_PROFILE_SCOPE] = PROFILE_SCOPE_DEFAULT
                    clone_payload["name"] = profile_json.get("display_name", user_input["name"])
                    await store.async_create_profile(
                        name=profile_json.get("display_name", user_input["name"]),
                        sensors=sensors,
                        clone_from=clone_payload,
                        scope=scope,
                    )
            self._new_profile_id = pid
            return await self.async_step_attach_sensors()
        profiles = {p.plant_id: p.display_name for p in registry.iter_profiles()}
        scope_selector = sel.SelectSelector(sel.SelectSelectorConfig(options=PROFILE_SCOPE_SELECTOR_OPTIONS))
        schema = vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required(CONF_PROFILE_SCOPE, default=PROFILE_SCOPE_DEFAULT): scope_selector,
                vol.Optional("copy_from"): vol.In(profiles) if profiles else str,
            }
        )
        return self.async_show_form(step_id="add_profile", data_schema=schema)

    async def async_step_manage_profiles(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        profiles = self._profiles()
        if not profiles:
            return self.async_abort(reason="no_profiles")

        if user_input is None:
            options = {pid: data.get("name", pid) for pid, data in profiles.items()}
            actions = {
                "edit_general": "Edit details",
                "edit_sensors": "Edit sensors",
                "edit_thresholds": "Edit targets",
                "delete": "Delete profile",
            }
            return self.async_show_form(
                step_id="manage_profiles",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile_id"): vol.In(options),
                        vol.Required("action", default="edit_general"): vol.In(actions),
                    }
                ),
            )

        self._pid = user_input["profile_id"]
        action = user_input["action"]
        if action == "edit_general":
            return await self.async_step_manage_profile_general()
        if action == "edit_sensors":
            return await self.async_step_manage_profile_sensors()
        if action == "edit_thresholds":
            return await self.async_step_manage_profile_thresholds()
        if action == "delete":
            return await self.async_step_manage_profile_delete()
        return self.async_abort(reason="unknown_profile")

    async def async_step_manage_profile_general(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        registry = await self._async_get_registry()
        profiles = self._profiles()
        if not self._pid or self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile = profiles[self._pid]
        general = profile.get("general", {}) if isinstance(profile.get("general"), Mapping) else {}
        defaults = {
            "name": profile.get("name", self._pid),
            "plant_type": general.get(CONF_PLANT_TYPE, profile.get("species_display", "")),
            CONF_PROFILE_SCOPE: general.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT),
            "species_display": profile.get("species_display", general.get("plant_type", "")),
        }
        scope_selector = sel.SelectSelector(sel.SelectSelectorConfig(options=PROFILE_SCOPE_SELECTOR_OPTIONS))
        schema = vol.Schema(
            {
                vol.Required("name", default=defaults["name"]): str,
                vol.Optional("plant_type", default=defaults["plant_type"]): str,
                vol.Required(CONF_PROFILE_SCOPE, default=defaults[CONF_PROFILE_SCOPE]): scope_selector,
                vol.Optional("species_display", default=defaults["species_display"]): str,
            }
        )

        errors: dict[str, str] = {}
        placeholders: dict[str, str] = {"profile": defaults["name"]}
        if user_input is not None:
            new_name = user_input["name"].strip()
            if not new_name:
                errors["name"] = "required"
            if not errors:
                try:
                    await registry.async_update_profile_general(
                        self._pid,
                        name=new_name,
                        plant_type=user_input.get("plant_type", "").strip() or None,
                        scope=user_input.get(CONF_PROFILE_SCOPE, PROFILE_SCOPE_DEFAULT),
                        species_display=user_input.get("species_display", "").strip() or None,
                    )
                except ValueError:
                    errors["base"] = "update_failed"
                else:
                    return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_general",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_manage_profile_sensors(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        registry = await self._async_get_registry()
        profiles = self._profiles()
        if not self._pid or self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile = profiles[self._pid]
        general = profile.get("general", {}) if isinstance(profile.get("general"), Mapping) else {}
        existing = general.get("sensors", {}) if isinstance(general.get("sensors"), Mapping) else {}
        description_placeholders = {
            "profile": profile.get("name") or self._pid,
            "error": "",
        }

        schema_fields: dict[Any, Any] = {}
        for measurement, selector in PROFILE_SENSOR_FIELDS.items():
            default_value = _default_sensor_value(existing.get(measurement))
            optional = (
                vol.Optional(measurement)
                if default_value is vol.UNDEFINED
                else vol.Optional(measurement, default=default_value)
            )
            schema_fields[optional] = vol.Any(selector, cv.string, vol.All([cv.string]))
        schema = vol.Schema(schema_fields)

        errors: dict[str, str] = {}
        if user_input is not None:
            sensors: dict[str, str | list[str]] = {}
            for measurement in PROFILE_SENSOR_FIELDS:
                raw = user_input.get(measurement)
                normalised = _normalise_sensor_submission(raw)
                if normalised is None:
                    continue
                sensors[measurement] = normalised
            try:
                await registry.async_set_profile_sensors(self._pid, sensors)
            except ValueError as err:
                errors["base"] = "sensor_validation_failed"
                description_placeholders["error"] = str(err)
            else:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_sensors",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_manage_profile_thresholds(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        registry = await self._async_get_registry()
        profiles = self._profiles()
        if not self._pid or self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile = profiles[self._pid]
        thresholds_payload = profile.get("thresholds") if isinstance(profile.get("thresholds"), Mapping) else {}
        resolved_payload = (
            profile.get("resolved_targets") if isinstance(profile.get("resolved_targets"), Mapping) else {}
        )

        def _resolve_default(key: str) -> str:
            if isinstance(thresholds_payload, Mapping):
                value = thresholds_payload.get(key)
                if isinstance(value, int | float):
                    return str(value)
                if isinstance(value, str) and value.strip():
                    return value
            if isinstance(resolved_payload, Mapping):
                value = resolved_payload.get(key)
                if isinstance(value, Mapping):
                    raw = value.get("value")
                    if isinstance(raw, int | float):
                        return str(raw)
                    if isinstance(raw, str) and raw.strip():
                        return raw
            return ""

        schema_fields: dict[Any, Any] = {}
        for key in MANUAL_THRESHOLD_FIELDS:
            schema_fields[vol.Optional(key, default=_resolve_default(key))] = vol.Any(str, int, float)
        schema = vol.Schema(schema_fields)

        errors: dict[str, str] = {}
        placeholders = {"profile": profile.get("name") or self._pid, "issue_detail": ""}

        if user_input is not None:
            cleaned: dict[str, float] = {}
            removed: set[str] = set()
            candidate = dict(thresholds_payload) if isinstance(thresholds_payload, Mapping) else {}

            for key in MANUAL_THRESHOLD_FIELDS:
                raw = user_input.get(key)
                if raw in (None, "", []):
                    if key in candidate:
                        candidate.pop(key, None)
                        removed.add(key)
                    continue
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    errors[key] = "invalid_float"
                    continue
                cleaned[key] = value
                candidate[key] = value

            if errors:
                return self.async_show_form(
                    step_id="manage_profile_thresholds",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders=placeholders,
                )

            violations = evaluate_threshold_bounds(candidate)
            if violations:
                placeholders["issue_detail"] = "\n".join(issue.message() for issue in violations[:3])
                for issue in violations:
                    if issue.key in MANUAL_THRESHOLD_FIELDS:
                        errors[issue.key] = "threshold_field_error"
                errors["base"] = "threshold_out_of_bounds"
                return self.async_show_form(
                    step_id="manage_profile_thresholds",
                    data_schema=schema,
                    errors=errors,
                    description_placeholders=placeholders,
                )

            target_keys = set(cleaned.keys()) | removed
            try:
                await registry.async_update_profile_thresholds(
                    self._pid,
                    cleaned,
                    allowed_keys=target_keys,
                    removed_keys=removed,
                )
            except ValueError as err:
                errors["base"] = "update_failed"
                placeholders["issue_detail"] = str(err)
            else:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_thresholds",
            data_schema=schema,
            errors=errors,
            description_placeholders=placeholders,
        )

    async def async_step_manage_profile_delete(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        registry = await self._async_get_registry()
        primary_id = get_primary_profile_id(self._entry)
        if not self._pid:
            return self.async_abort(reason="unknown_profile")
        if self._pid == primary_id:
            return self.async_abort(reason="cannot_delete_primary")

        profiles = self._profiles()
        if self._pid not in profiles:
            return self.async_abort(reason="unknown_profile")

        profile_name = profiles[self._pid].get("name") or self._pid
        schema = vol.Schema({vol.Required("confirm", default=False): bool})
        placeholders = {"profile": profile_name}

        if user_input is not None:
            if user_input.get("confirm"):
                try:
                    await registry.async_delete_profile(self._pid)
                except ValueError:
                    return self.async_abort(reason="unknown_profile")
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="manage_profile_delete",
            data_schema=schema,
            description_placeholders=placeholders,
        )

    async def async_step_configure_ai(self, user_input: dict[str, Any] | None = None):
        opts = dict(self._entry.options)
        defaults = {
            CONF_API_KEY: opts.get(CONF_API_KEY, self._entry.data.get(CONF_API_KEY, "")),
            CONF_MODEL: opts.get(CONF_MODEL, self._entry.data.get(CONF_MODEL, DEFAULT_MODEL)),
            CONF_BASE_URL: opts.get(CONF_BASE_URL, self._entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)),
            CONF_UPDATE_INTERVAL: opts.get(
                CONF_UPDATE_INTERVAL,
                self._entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_MINUTES),
            ),
        }

        schema = vol.Schema(
            {
                vol.Optional(CONF_API_KEY, default=defaults[CONF_API_KEY]): sel.TextSelector(
                    sel.TextSelectorConfig(type="password")
                ),
                vol.Optional(CONF_MODEL, default=defaults[CONF_MODEL]): str,
                vol.Optional(CONF_BASE_URL, default=defaults[CONF_BASE_URL]): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=defaults[CONF_UPDATE_INTERVAL]): vol.All(
                    int, vol.Range(min=1, max=60)
                ),
            }
        )

        if user_input is not None:
            new_options = {**opts}
            for key, value in user_input.items():
                if value in (None, ""):
                    new_options.pop(key, None)
                else:
                    new_options[key] = value
            return self.async_create_entry(title="AI settings updated", data=new_options)

        return self.async_show_form(step_id="configure_ai", data_schema=schema)

    async def async_step_attach_sensors(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        from .profile_registry import ProfileRegistry

        registry: ProfileRegistry = self.hass.data[DOMAIN]["registry"]
        pid = self._new_profile_id
        errors: dict[str, str] = {}
        if user_input is not None and pid:
            sensors: dict[str, str] = {}
            for role in ("temperature", "humidity", "illuminance", "moisture"):
                if ent := user_input.get(role):
                    sensors[role] = ent

            skip_requested = bool(user_input.get("skip_linking"))
            if not sensors or skip_requested:
                self._clear_sensor_warning()
                if pid:
                    await registry.async_link_sensors(pid, {})
                return self.async_create_entry(title="", data={})

            validation = validate_sensor_links(self.hass, sensors)
            for issue in validation.errors:
                errors[issue.role] = issue.issue
            if validation.warnings:
                self._notify_sensor_warnings(validation.warnings)
            else:
                self._clear_sensor_warning()
            if not errors:
                await registry.async_link_sensors(pid, sensors)
                return self.async_create_entry(title="", data={})
        schema = vol.Schema(
            {
                vol.Optional("temperature"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["temperature"])
                ),
                vol.Optional("humidity"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["humidity"])
                ),
                vol.Optional("illuminance"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["illuminance"])
                ),
                vol.Optional("moisture"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain=["sensor"], device_class=["moisture"])
                ),
                vol.Optional("skip_linking", default=False): bool,
            }
        )
        return self.async_show_form(step_id="attach_sensors", data_schema=schema, errors=errors)

    async def async_step_calibration(self, user_input=None):
        schema = vol.Schema(
            {
                vol.Required("lux_entity_id"): sel.EntitySelector(
                    sel.EntitySelectorConfig(domain="sensor", device_class="illuminance")
                ),
                vol.Optional("ppfd_entity_id"): sel.EntitySelector(sel.EntitySelectorConfig(domain="sensor")),
                vol.Optional("model", default="linear"): vol.In(["linear", "quadratic", "power"]),
                vol.Optional("averaging_seconds", default=3): int,
                vol.Optional("notes"): str,
            }
        )
        if user_input is not None:
            res = await self.hass.services.async_call(
                DOMAIN,
                "start_calibration",
                user_input,
                blocking=True,
                return_response=True,
            )
            self._cal_session = res.get("session_id")
            return await self.async_step_calibration_collect()
        return self.async_show_form(step_id="calibration", data_schema=schema)

    async def async_step_calibration_collect(self, user_input=None):
        schema = vol.Schema(
            {
                vol.Required("action", default="add"): vol.In(
                    [
                        "add",
                        "finish",
                        "abort",
                    ]
                ),
                vol.Optional("ppfd_value"): float,
            }
        )
        if user_input is not None and self._cal_session:
            action = user_input["action"]
            if action == "add":
                data = {"session_id": self._cal_session}
                if user_input.get("ppfd_value") is not None:
                    data["ppfd_value"] = user_input["ppfd_value"]
                await self.hass.services.async_call(DOMAIN, "add_calibration_point", data, blocking=True)
                return await self.async_step_calibration_collect()
            if action == "finish":
                await self.hass.services.async_call(
                    DOMAIN,
                    "finish_calibration",
                    {"session_id": self._cal_session},
                    blocking=True,
                )
                return self.async_create_entry(title="calibration", data={})
            if action == "abort":
                await self.hass.services.async_call(
                    DOMAIN,
                    "abort_calibration",
                    {"session_id": self._cal_session},
                    blocking=True,
                )
                return self.async_create_entry(title="calibration", data={})
        return self.async_show_form(step_id="calibration_collect", data_schema=schema)

    # --- Per-variable source editing ---

    async def async_step_profile(self, user_input=None):
        profiles = self._profiles()
        if user_input is not None:
            self._pid = user_input["profile_id"]
            return await self.async_step_action()
        return self.async_show_form(
            step_id="profile",
            data_schema=vol.Schema(
                {vol.Required("profile_id"): vol.In({pid: p["name"] for pid, p in profiles.items()})}
            ),
        )

    async def async_step_action(self, user_input=None):
        actions = {"edit": "Edit variable", "generate": "Generate profile"}
        if user_input is not None:
            act = user_input["action"]
            if act == "edit":
                return await self.async_step_pick_variable()
            return await self.async_step_generate()
        return self.async_show_form(
            step_id="action",
            data_schema=vol.Schema({vol.Required("action"): vol.In(actions)}),
        )

    async def async_step_pick_variable(self, user_input=None):
        from .const import VARIABLE_SPECS

        if user_input is not None:
            self._var = user_input["variable"]
            return await self.async_step_pick_source()
        return self.async_show_form(
            step_id="pick_variable",
            data_schema=vol.Schema({vol.Required("variable"): vol.In([k for k, *_ in VARIABLE_SPECS])}),
        )

    async def async_step_pick_source(self, user_input=None):
        from .const import SOURCES

        if user_input is not None:
            self._mode = user_input["mode"]
            if self._mode == "manual":
                return await self.async_step_src_manual()
            if self._mode == "clone":
                return await self.async_step_src_clone()
            if self._mode == "opb":
                return await self.async_step_src_opb()
            if self._mode == "ai":
                return await self.async_step_src_ai()
        return self.async_show_form(
            step_id="pick_source",
            data_schema=vol.Schema({vol.Required("mode"): vol.In(SOURCES)}),
        )

    async def async_step_src_manual(self, user_input=None):
        if user_input is not None:
            self._set_source({"mode": "manual", "value": float(user_input["value"])})
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_manual",
            data_schema=vol.Schema({vol.Required("value"): float}),
        )

    async def async_step_src_clone(self, user_input=None):
        profs = {pid: p["name"] for pid, p in self._profiles().items() if pid != self._pid}
        if user_input is not None:
            self._set_source({"mode": "clone", "copy_from": user_input["copy_from"]})
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_clone",
            data_schema=vol.Schema({vol.Required("copy_from"): vol.In(profs)}),
        )

    async def async_step_src_opb(self, user_input=None):
        if user_input is not None:
            self._set_source(
                {
                    "mode": "opb",
                    "opb": {"species": user_input["species"], "field": user_input["field"]},
                }
            )
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_opb",
            data_schema=vol.Schema({vol.Required("species"): str, vol.Required("field"): str}),
        )

    async def async_step_src_ai(self, user_input=None):
        if user_input is not None:
            self._set_source(
                {
                    "mode": "ai",
                    "ai": {
                        "provider": user_input.get("provider", "openai"),
                        "model": user_input.get("model", "gpt-4o-mini"),
                        "ttl_hours": int(user_input.get("ttl_hours", 720)),
                    },
                }
            )
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="src_ai",
            data_schema=vol.Schema(
                {
                    vol.Optional("provider", default="openai"): str,
                    vol.Optional("model", default="gpt-4o-mini"): str,
                    vol.Optional("ttl_hours", default=720): int,
                }
            ),
        )

    async def async_step_generate(self, user_input=None):
        if user_input is not None:
            mode = user_input["mode"]
            if mode == "clone":
                return await self.async_step_generate_clone()
            self._generate_all(mode)
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="generate",
            data_schema=vol.Schema({vol.Required("mode"): vol.In(["clone", "opb", "ai"])}),
        )

    async def async_step_generate_clone(self, user_input=None):
        profs = {pid: p["name"] for pid, p in self._profiles().items() if pid != self._pid}
        if user_input is not None:
            self._generate_all("clone", user_input["copy_from"])
            return await self.async_step_apply()
        return self.async_show_form(
            step_id="generate_clone",
            data_schema=vol.Schema({vol.Required("copy_from"): vol.In(profs)}),
        )

    def _profiles(self):
        profiles: dict[str, dict[str, Any]] = {}
        for pid, payload in (self._entry.options.get(CONF_PROFILES, {}) or {}).items():
            copy = dict(payload)
            ensure_sections(copy, plant_id=pid, display_name=copy.get("name") or pid)
            profiles[pid] = copy
        return profiles

    def _set_source(self, src: dict):
        opts = dict(self._entry.options)
        prof = dict(opts.get(CONF_PROFILES, {}).get(self._pid, {}))
        ensure_sections(prof, plant_id=self._pid, display_name=prof.get("name") or self._pid)
        sources = dict(prof.get("sources", {}))
        sources[self._var] = src
        prof["sources"] = sources
        prof["needs_resolution"] = True
        allp = dict(opts.get(CONF_PROFILES, {}))
        allp[self._pid] = prof
        opts[CONF_PROFILES] = allp
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

    def _generate_all(self, mode: str, source_profile_id: str | None = None):
        from .const import VARIABLE_SPECS

        opts = dict(self._entry.options)
        prof = dict(opts.get(CONF_PROFILES, {}).get(self._pid, {}))
        library_section, local_section = ensure_sections(
            prof,
            plant_id=self._pid,
            display_name=prof.get("name") or self._pid,
        )
        sources = dict(prof.get("sources", {}))
        slug = determine_species_slug(
            library=library_section,
            local=local_section,
            raw=prof.get("species"),
        )
        if mode == "clone":
            if not source_profile_id:
                raise ValueError("source_profile_id required for clone")
            other = dict(opts.get(CONF_PROFILES, {}).get(source_profile_id, {}))
            ensure_sections(
                other,
                plant_id=source_profile_id,
                display_name=other.get("name") or source_profile_id,
            )
            prof["thresholds"] = dict(other.get("thresholds", {}))
            if isinstance(other.get("resolved_targets"), dict):
                prof["resolved_targets"] = deepcopy(other.get("resolved_targets"))
            else:
                prof.pop("resolved_targets", None)
            if isinstance(other.get("variables"), dict):
                prof["variables"] = deepcopy(other.get("variables"))
            else:
                prof.pop("variables", None)
            sync_thresholds(prof, default_source="clone")
            for key, *_ in VARIABLE_SPECS:
                sources[key] = {"mode": "clone", "copy_from": source_profile_id}
        else:
            for key, *_ in VARIABLE_SPECS:
                if mode == "opb":
                    sources[key] = {"mode": "opb", "opb": {"species": slug, "field": key}}
                else:
                    sources[key] = {
                        "mode": "ai",
                        "ai": {
                            "provider": "openai",
                            "model": "gpt-4o-mini",
                            "ttl_hours": 720,
                        },
                    }
        prof["sources"] = sources
        prof["needs_resolution"] = True
        allp = dict(opts.get(CONF_PROFILES, {}))
        allp[self._pid] = prof
        opts[CONF_PROFILES] = allp
        self.hass.config_entries.async_update_entry(self._entry, options=opts)

    def _infer_nutrient_schedule_plant_type(self, profile: Mapping[str, Any]) -> str | None:
        """Return the best available species or plant-type identifier for a profile."""

        def _as_str(value: Any) -> str | None:
            if isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    return candidate
            return None

        containers: list[Mapping[str, Any]] = []
        local_section = profile.get("local")
        if isinstance(local_section, Mapping):
            containers.append(local_section)
            general = local_section.get("general")
            if isinstance(general, Mapping):
                containers.append(general)
        general_section = profile.get("general")
        if isinstance(general_section, Mapping):
            containers.append(general_section)

        sections = profile.get("sections")
        if isinstance(sections, Mapping):
            local = sections.get("local")
            if isinstance(local, Mapping):
                general = local.get("general")
                if isinstance(general, Mapping):
                    containers.append(general)

        for container in containers:
            for field in ("plant_type", "species", "slug"):
                candidate = _as_str(container.get(field))
                if candidate:
                    return candidate

        for field in ("species", "plant_type", "species_display"):
            candidate = _as_str(profile.get(field))
            if candidate:
                return candidate

        library = profile.get("library")
        if isinstance(library, Mapping):
            for key in ("identity", "taxonomy"):
                payload = library.get(key)
                if not isinstance(payload, Mapping):
                    continue
                for field in ("plant_type", "species", "binomial", "slug", "name"):
                    candidate = _as_str(payload.get(field))
                    if candidate:
                        return candidate

        if isinstance(sections, Mapping):
            library_section = sections.get("library")
            if isinstance(library_section, Mapping):
                for key in ("identity", "taxonomy"):
                    payload = library_section.get(key)
                    if not isinstance(payload, Mapping):
                        continue
                    for field in ("plant_type", "species", "binomial", "slug", "name"):
                        candidate = _as_str(payload.get(field))
                        if candidate:
                            return candidate

        return None

    def _extract_nutrient_schedule(self, profile: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Extract the stored nutrient schedule for ``profile`` if one exists."""

        def _schedule_from(container: Mapping[str, Any] | None) -> list[dict[str, Any]] | None:
            if not isinstance(container, Mapping):
                return None
            schedule = container.get("nutrient_schedule")
            if isinstance(schedule, list):
                return [dict(item) for item in schedule if isinstance(item, Mapping)]
            nutrients = container.get("nutrients")
            if isinstance(nutrients, Mapping):
                schedule = nutrients.get("schedule")
                if isinstance(schedule, list):
                    return [dict(item) for item in schedule if isinstance(item, Mapping)]
            metadata = container.get("metadata")
            if isinstance(metadata, Mapping):
                schedule = metadata.get("nutrient_schedule")
                if isinstance(schedule, list):
                    return [dict(item) for item in schedule if isinstance(item, Mapping)]
            return None

        containers: list[Mapping[str, Any] | None] = [
            profile.get("local"),
            profile.get("general"),
        ]
        local_section = profile.get("local")
        if isinstance(local_section, Mapping):
            containers.append(local_section.get("general"))
        sections = profile.get("sections")
        if isinstance(sections, Mapping):
            local = sections.get("local")
            if isinstance(local, Mapping):
                containers.append(local.get("general"))
        containers.append(profile)

        for container in containers:
            schedule = _schedule_from(container)
            if schedule:
                return schedule
        return []

    def _generate_schedule_for_profile(self, profile: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Generate a nutrient schedule payload for ``profile`` using heuristics."""

        plant_type = self._infer_nutrient_schedule_plant_type(profile)
        if not plant_type:
            raise ValueError("missing_plant_type")

        stages = generate_nutrient_schedule(plant_type)
        if not stages:
            raise ValueError("no_schedule")

        schedule: list[dict[str, Any]] = []
        current_day = 1
        for index, stage in enumerate(stages, start=1):
            stage_name = getattr(stage, "stage", None) or getattr(stage, "name", None) or f"stage_{index}"
            try:
                duration = int(getattr(stage, "duration_days", 0) or 0)
            except (TypeError, ValueError):  # pragma: no cover - defensive
                duration = 0
            totals_raw = getattr(stage, "totals", {})
            if not isinstance(totals_raw, Mapping):
                totals_raw = {}
            totals: dict[str, float] = {}
            for nutrient, amount in totals_raw.items():
                if nutrient is None:
                    continue
                try:
                    totals[str(nutrient)] = float(amount)
                except (TypeError, ValueError):
                    continue

            entry: dict[str, Any] = {
                "stage": str(stage_name),
                "duration_days": max(duration, 0),
                "totals_mg": totals,
                "source": "auto_generate",
            }
            if entry["duration_days"] > 0:
                entry["start_day"] = current_day
                entry["end_day"] = current_day + entry["duration_days"] - 1
                entry["daily_mg"] = {
                    nutrient: round(amount / entry["duration_days"], 4) for nutrient, amount in totals.items()
                }
                current_day = entry["end_day"] + 1
            else:
                entry["start_day"] = current_day
                entry["end_day"] = current_day
                if totals:
                    entry["daily_mg"] = dict(totals)
            schedule.append(entry)

        return schedule

    def _coerce_schedule_row(self, item: Any) -> dict[str, Any]:
        """Normalise a raw nutrient schedule entry."""

        if not isinstance(item, Mapping):
            raise ValueError("schedule_row_not_mapping")

        def _as_str(value: Any) -> str | None:
            if isinstance(value, str):
                candidate = value.strip()
                if candidate:
                    return candidate
            return None

        stage = _as_str(item.get("stage") or item.get("name") or item.get("phase"))
        if not stage:
            raise ValueError("missing_stage")

        duration_raw = item.get("duration_days") or item.get("duration") or item.get("days") or item.get("length_days")
        try:
            duration = int(float(duration_raw)) if duration_raw is not None else None
        except (TypeError, ValueError) as err:  # pragma: no cover - defensive
            raise ValueError("invalid_duration") from err
        if duration is None or duration < 0:
            raise ValueError("invalid_duration")

        totals: dict[str, float] = {}
        totals_raw = item.get("totals_mg") or item.get("totals") or item.get("nutrients") or item.get("targets")
        if isinstance(totals_raw, Mapping):
            for nutrient, amount in totals_raw.items():
                name = _as_str(nutrient) or str(nutrient)
                try:
                    totals[name] = float(amount)
                except (TypeError, ValueError):
                    continue
        elif isinstance(totals_raw, list):
            for entry in totals_raw:
                if not isinstance(entry, Mapping):
                    continue
                nutrient = _as_str(entry.get("nutrient") or entry.get("id") or entry.get("name"))
                if not nutrient:
                    continue
                try:
                    totals[nutrient] = float(entry.get("value") or entry.get("amount"))
                except (TypeError, ValueError):
                    continue

        def _as_int(value: Any) -> int | None:
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return None

        start_day = _as_int(item.get("start_day") or item.get("day_start") or item.get("start"))
        end_day = _as_int(item.get("end_day") or item.get("day_end") or item.get("end"))

        result: dict[str, Any] = {
            "stage": stage,
            "duration_days": duration,
            "totals_mg": totals,
        }
        if start_day is not None:
            result["start_day"] = start_day
        if end_day is None and start_day is not None and duration > 0:
            end_day = start_day + duration - 1
        if end_day is not None:
            result["end_day"] = end_day
        if totals:
            if duration > 0:
                result["daily_mg"] = {nutrient: round(amount / duration, 4) for nutrient, amount in totals.items()}
            else:
                result["daily_mg"] = dict(totals)

        notes = _as_str(item.get("notes") or item.get("description"))
        if notes:
            result["notes"] = notes
        source = _as_str(item.get("source") or item.get("mode"))
        if source:
            result["source"] = source

        return result

    def _apply_nutrient_schedule(self, profile_id: str | None, schedule: list[dict[str, Any]]) -> None:
        """Persist ``schedule`` to the config entry options for ``profile_id``."""

        if not profile_id:
            return

        safe_schedule = json.loads(json.dumps(schedule, ensure_ascii=False))
        opts = dict(self._entry.options)
        profiles = dict(opts.get(CONF_PROFILES, {}))
        profile = dict(profiles.get(profile_id, {}))

        ensure_sections(profile, plant_id=profile_id, display_name=profile.get("name") or profile_id)

        local = profile.get("local")
        local_dict = dict(local) if isinstance(local, Mapping) else {}
        general_local = local_dict.get("general")
        general_local_dict = dict(general_local) if isinstance(general_local, Mapping) else {}
        general_local_dict["nutrient_schedule"] = safe_schedule
        local_dict["general"] = general_local_dict
        profile["local"] = local_dict

        general = profile.get("general")
        general_dict = dict(general) if isinstance(general, Mapping) else {}
        general_dict["nutrient_schedule"] = safe_schedule
        profile["general"] = general_dict

        profiles[profile_id] = profile
        opts[CONF_PROFILES] = profiles
        self.hass.config_entries.async_update_entry(self._entry, options=opts)
        self._entry.options = opts

    async def async_step_apply(self, user_input=None):
        if user_input is not None:
            if user_input.get("resolve_now"):
                from .resolver import PreferenceResolver

                await PreferenceResolver(self.hass).resolve_profile(self._entry, self._pid)
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="apply",
            data_schema=vol.Schema({vol.Optional("resolve_now", default=True): bool}),
        )


# Backwards compatibility for older imports
class HorticultureAssistantConfigFlow(ConfigFlow):
    """Retain legacy class name for tests and external references."""

    pass
