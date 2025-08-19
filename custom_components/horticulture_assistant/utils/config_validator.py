"""Configuration validation utilities for Horticulture Assistant."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigValidator:
    """Validates configuration and creates issues for problems."""

    def __init__(self, hass: HomeAssistant):
        self.hass = hass

    def validate_sensor_entities(self, plant_id: str, sensors: Dict[str, List[str]]) -> List[str]:
        """Validate that all sensor entities exist and return list of missing ones."""
        missing_entities = []

        for sensor_type, entity_ids in sensors.items():
            for entity_id in entity_ids:
                if self.hass.states.get(entity_id) is None:
                    missing_entities.append(entity_id)
                    self._create_missing_entity_issue(plant_id, entity_id)
                    _LOGGER.warning("Missing sensor entity %s for plant %s", entity_id, plant_id)

        return missing_entities

    def validate_plant_profile(self, plant_id: str, profile: Dict[str, Any]) -> List[str]:
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

    def _create_missing_entity_issue(self, plant_id: str, entity_id: str) -> None:
        """Create a Home Assistant issue for missing entity."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"missing_entity_{plant_id}_{entity_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="missing_entity",
            translation_placeholders={"plant_id": plant_id, "entity_id": entity_id},
        )

    def validate_api_config(self, api_key: str, base_url: str) -> List[str]:
        """Validate API configuration."""
        errors = []

        if not api_key:
            errors.append("API key is required")
        elif len(api_key) < 10:
            errors.append("API key appears to be too short")

        if not base_url.startswith(("http://", "https://")):
            errors.append("Base URL must start with http:// or https://")

        return errors
