"""Configuration validation utilities for Horticulture Assistant."""

from __future__ import annotations

import logging
import re
from typing import Any

try:  # pragma: no cover - executed when Home Assistant is installed
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import issue_registry as ir
except (ImportError, ModuleNotFoundError):  # pragma: no cover - executed in tests
    from enum import StrEnum
    from types import SimpleNamespace

    HomeAssistant = object  # type: ignore[misc,assignment]

    class _IssueSeverity(StrEnum):
        WARNING = "warning"

    ir = SimpleNamespace(  # type: ignore[assignment]
        IssueSeverity=_IssueSeverity,
        async_create_issue=lambda *_args, **_kwargs: None,
    )

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigValidator:
    """Validates configuration and creates issues for problems."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    def validate_sensor_entities(self, plant_id: str, sensors: dict[str, list[str]]) -> list[str]:
        """Validate that all sensor entities exist and return list of missing ones."""
        missing_entities = []

        for _sensor_type, entity_ids in sensors.items():
            for entity_id in entity_ids:
                if self.hass.states.get(entity_id) is None:
                    missing_entities.append(entity_id)
                    self._create_missing_entity_issue(plant_id, entity_id)
                    _LOGGER.warning("Missing sensor entity %s for plant %s", entity_id, plant_id)

        return missing_entities

    def validate_plant_profile(self, plant_id: str, profile: dict[str, Any]) -> list[str]:
        """Validate plant profile structure and return list of errors."""
        errors = []

        # Check required fields
        required_fields = ["name", "plant_type"]
        for field in required_fields:
            if field not in profile:
                errors.append(f"Missing required field: {field}")

        # Validate plant type
        if "plant_type" in profile:
            valid_types = ["tomato", "lettuce", "herbs", "citrus", "strawberry"]
            if profile["plant_type"] not in valid_types:
                errors.append(f"Invalid plant_type: {profile['plant_type']}")

        # Validate stages if present
        if "stages" in profile:
            if not isinstance(profile["stages"], dict):
                errors.append("stages must be a dictionary")
            else:
                for stage_name, stage_data in profile["stages"].items():
                    if not isinstance(stage_data, dict):
                        errors.append(f"Stage {stage_name} must be a dictionary")

        return errors

    @staticmethod
    def _issue_id_component(value: str) -> str:
        """Return an issue-id-safe slug for ``value``.

        Home Assistant's issue registry only accepts identifiers matching
        ``^[a-z0-9_]+$``. Plant IDs and entity IDs regularly contain characters
        such as spaces, dots or dashes which would otherwise cause
        ``ValueError`` to be raised when registering the issue. Sanitising the
        components ensures we always produce valid identifiers while remaining
        deterministic.
        """

        slug = re.sub(r"[^a-z0-9_]", "_", value.lower())
        slug = re.sub(r"_+", "_", slug).strip("_")
        return slug or "unknown"

    def _create_missing_entity_issue(self, plant_id: str, entity_id: str) -> None:
        """Create a Home Assistant issue for missing entity."""
        plant_component = self._issue_id_component(plant_id)
        entity_component = self._issue_id_component(entity_id)
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"missing_entity_{plant_component}_{entity_component}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_entity",
            translation_placeholders={"plant_id": plant_id, "entity_id": entity_id},
        )

    def validate_api_config(self, api_key: str | None, base_url: str | None) -> list[str]:
        """Validate API configuration.

        The configuration flow presents text inputs, but defensive guards are
        required to account for unexpected ``None`` values or other object
        types.  Previous implementations assumed ``str`` values which caused an
        ``AttributeError`` when Home Assistant supplied ``None`` during option
        updates.  Normalising the inputs up-front keeps the validation resilient
        and ensures the user receives actionable error messages instead of a
        stack trace.
        """

        errors: list[str] = []

        api_value = api_key.strip() if isinstance(api_key, str) else ""
        if not api_value:
            errors.append("API key is required")
        elif len(api_value) < 10:
            errors.append("API key appears to be too short")

        base_value = base_url.strip() if isinstance(base_url, str) else ""
        if base_value and not base_value.startswith(("http://", "https://")):
            errors.append("Base URL must start with http:// or https://")

        return errors
