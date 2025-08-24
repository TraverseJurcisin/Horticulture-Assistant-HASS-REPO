import json
import logging
import os
import re
from pathlib import Path

from custom_components.horticulture_assistant.utils.path_utils import plants_path

try:
    from homeassistant.core import HomeAssistant
except ImportError:
    HomeAssistant = None  # Allow usage outside Home Assistant for testing

_LOGGER = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Helper to slugify a string (lowercase, underscores for non-alphanumeric)."""
    text = text.lower()
    text = re.sub(r'[^0-9a-z_]+', '_', text)
    text = text.strip('_')
    # Collapse multiple underscores
    while '__' in text:
        text = text.replace('__', '_')
    return text


def generate_profile(
    metadata: dict, hass: 'HomeAssistant' = None, overwrite: bool = False, base_dir: str = None
) -> str:
    """
    Generate a new plant profile directory with template JSON files.

    Accepts input metadata for a plant (e.g. name, cultivar, crop type, tags, zone, stage length, etc.)
    and scaffolds a set of JSON profile files (general.json, environment.json, nutrition.json, irrigation.json, stages.json)
    into plants/<plant_id>/.

    Unknown or unspecified values are filled with placeholders (null or "TBD").
    Existing files are skipped by default unless overwrite is True.

    :param metadata: Dictionary of plant metadata (name/display_name/plant_name,
        cultivar, plant_type, tags, zone, stage_length, etc.)
    :param hass: HomeAssistant instance for path resolution (optional).
    :param overwrite: If True, overwrite existing files; if False, skip writing files that already exist.
    :param base_dir: Base directory for plant profiles (defaults to "plants/" in current working directory or Home Assistant config).
    :return: The plant_id of the generated profile (string), or an empty string on error.
    """
    # Determine the plant identifier (plant_id)
    plant_id = metadata.get("plant_id") or metadata.get("id")
    display_name = (
        metadata.get("display_name") or metadata.get("name") or metadata.get("plant_name")
    )
    if not plant_id:
        if display_name:
            plant_id = _slugify(display_name)
            _LOGGER.debug("Generated plant_id '%s' from display_name '%s'.", plant_id, display_name)
        else:
            # Fallback: try plant_type or cultivar as identifier
            if metadata.get("plant_type"):
                plant_id = _slugify(str(metadata["plant_type"]))
                _LOGGER.warning("No name provided; using plant_type '%s' as plant_id.", plant_id)
            elif metadata.get("cultivar"):
                plant_id = _slugify(str(metadata["cultivar"]))
                _LOGGER.warning("No name provided; using cultivar '%s' as plant_id.", plant_id)
            else:
                _LOGGER.error("No plant_id or name provided in metadata; cannot generate profile.")
                return ""

    # Determine base directory for plant profiles
    if base_dir:
        base_path = Path(base_dir)
    elif hass is not None:
        try:
            base_path = Path(plants_path(hass))
        except Exception as e:
            _LOGGER.error("Error resolving Home Assistant plants directory: %s", e)
            base_path = Path(plants_path(None))
    else:
        base_path = Path("plants")

    plant_dir = base_path / plant_id
    try:
        os.makedirs(plant_dir, exist_ok=True)
    except Exception as e:
        _LOGGER.error("Failed to create directory %s: %s", plant_dir, e)
        return ""

    # Prepare general profile data with placeholders for missing values
    plant_type_val = metadata.get("plant_type") or metadata.get("crop_type") or ""
    cultivar_val = metadata.get("cultivar") or ""
    species_val = metadata.get("species") or ""
    location_val = metadata.get("location") or ""

    general_data = {
        "plant_id": plant_id,
        "display_name": display_name if display_name else "TBD",
        "plant_type": _slugify(str(plant_type_val)) if plant_type_val else "TBD",
        "cultivar": _slugify(str(cultivar_val)) if cultivar_val else "TBD",
        "species": species_val if species_val else "TBD",
        "location": location_val if location_val else "TBD",
        "zone_id": metadata.get("zone_id") or None,
    }
    if "start_date" in metadata:
        general_data["start_date"] = metadata["start_date"]

    # Determine lifecycle stage (use provided or infer from tags)
    lifecycle_stage = metadata.get("current_lifecycle_stage") or metadata.get("lifecycle_stage")
    if lifecycle_stage is None and "tags" in metadata:
        for tag in metadata["tags"]:
            tag_lower = str(tag).lower()
            if tag_lower in {"seedling", "vegetative", "flowering", "fruiting", "dormant"}:
                lifecycle_stage = tag_lower
                break
    general_data["lifecycle_stage"] = lifecycle_stage if lifecycle_stage is not None else "TBD"

    # Set automation flags (default to False if not provided)
    general_data["auto_lifecycle_mode"] = (
        bool(metadata.get("auto_lifecycle") or metadata.get("auto_lifecycle_mode"))
        if ("auto_lifecycle" in metadata or "auto_lifecycle_mode" in metadata)
        else False
    )
    general_data["auto_approve_all"] = (
        bool(metadata.get("auto_approve_actions") or metadata.get("auto_approve_all"))
        if ("auto_approve_actions" in metadata or "auto_approve_all" in metadata)
        else False
    )

    # Compile tags from provided list and known metadata fields
    tags = []
    if "tags" in metadata and isinstance(metadata["tags"], list | tuple):
        tags = list(metadata["tags"])
    tags_lower = [str(t).lower() for t in tags]

    # Include plant_type, cultivar, stage, zone, etc. as tags if not already present and not placeholders
    pt_slug = general_data["plant_type"]
    if pt_slug and pt_slug.lower() != "tbd" and pt_slug.lower() not in tags_lower:
        tags.append(pt_slug)
        tags_lower.append(pt_slug.lower())
    cv_slug = general_data["cultivar"]
    if cv_slug and cv_slug.lower() != "tbd" and cv_slug.lower() not in tags_lower:
        tags.append(cv_slug)
        tags_lower.append(cv_slug.lower())
    stage_tag = general_data["lifecycle_stage"]
    if stage_tag and stage_tag.lower() != "tbd" and stage_tag.lower() not in tags_lower:
        tags.append(stage_tag)
        tags_lower.append(stage_tag.lower())
    zone_val = metadata.get("zone") or metadata.get("hardiness_zone")
    if zone_val:
        zone_tag = f"zone_{str(zone_val).lower()}"
        if zone_tag not in tags_lower:
            tags.append(zone_tag)
            tags_lower.append(zone_tag)
    if "start_date" in general_data:
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(str(general_data["start_date"]))
            year = dt.year
            month = dt.month
            season = (
                "winter"
                if month in (12, 1, 2)
                else "spring"
                if month in (3, 4, 5)
                else "summer"
                if month in (6, 7, 8)
                else "fall"
            )
            season_tag = f"{season}_{year}"
            if season_tag not in tags_lower:
                tags.append(season_tag)
                tags_lower.append(season_tag)
        except Exception as e:
            _LOGGER.debug("Could not derive season tag from start_date: %s", e)
    loc_val = general_data["location"]
    if loc_val and loc_val.lower() != "tbd" and loc_val.lower() not in tags_lower:
        tags.append(loc_val)
        tags_lower.append(loc_val.lower())

    # Normalize all tags to lowercase slug format (underscored)
    normalized_tags = []
    seen_tags = set()
    for tag in tags:
        t = str(tag).lower()
        slug = re.sub(r'[^0-9a-z_]+', '_', t).strip('_')
        # Collapse multiple underscores in tag slug
        while '__' in slug:
            slug = slug.replace('__', '_')
        if slug and slug not in seen_tags:
            normalized_tags.append(slug)
            seen_tags.add(slug)
    general_data["tags"] = normalized_tags

    # Placeholders for sensor and actuator entity mappings (to be filled later)
    general_data["sensor_entities"] = {
        "moisture_sensors": metadata.get("moisture_sensors", []),
        "temperature_sensors": metadata.get("temperature_sensors", []),
    }
    general_data["actuator_entities"] = {}

    # Environment profile section (environmental thresholds and conditions)
    environment_data = {
        "light": None,
        "temperature": None,
        "humidity": None,
        "hardiness_zone": str(zone_val) if zone_val else "TBD",
        "EC": None,
        "pH": None,
    }

    # Nutrition profile section (nutrient thresholds placeholders in ppm)
    nutrition_data = {
        "leaf_nitrogen_ppm": None,
        "leaf_phosphorus_ppm": None,
        "leaf_potassium_ppm": None,
        "leaf_calcium_ppm": None,
        "leaf_magnesium_ppm": None,
        "leaf_sulfur_ppm": None,
        "leaf_iron_ppm": None,
        "leaf_manganese_ppm": None,
        "leaf_zinc_ppm": None,
        "leaf_copper_ppm": None,
        "leaf_boron_ppm": None,
        "leaf_molybdenum_ppm": None,
        "leaf_chlorine_ppm": None,
        "leaf_arsenic_ppm": None,
        "leaf_cadmium_ppm": None,
        "leaf_lead_ppm": None,
        "leaf_mercury_ppm": None,
        "leaf_nickel_ppm": None,
        "leaf_cobalt_ppm": None,
        "leaf_selenium_ppm": None,
    }

    # Irrigation profile section (irrigation settings/thresholds)
    irrigation_data = {"soil_moisture_pct": None}

    # Stages profile section (growth stages and durations)
    stage_name = (
        general_data["lifecycle_stage"]
        if general_data.get("lifecycle_stage") not in (None, "", "TBD")
        else "initial_stage"
    )
    provided_stage_len = metadata.get("stage_length") or metadata.get("stage_duration")
    stage_duration_val = None
    if provided_stage_len is not None:
        try:
            stage_duration_val = float(str(provided_stage_len).split()[0])
        except Exception:
            try:
                stage_duration_val = float(provided_stage_len)
            except Exception:
                stage_duration_val = None
    stages_data = {
        stage_name: {
            "stage_duration": stage_duration_val if stage_duration_val is not None else None,
            "notes": "TBD",
        }
    }

    # Write each profile section to its JSON file
    profile_sections = {
        "general.json": general_data,
        "environment.json": environment_data,
        "nutrition.json": nutrition_data,
        "irrigation.json": irrigation_data,
        "stages.json": stages_data,
    }
    for filename, data in profile_sections.items():
        file_path = plant_dir / filename
        if file_path.exists() and not overwrite:
            _LOGGER.info("File %s already exists. Skipping write.", file_path)
            continue
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if file_path.exists() and overwrite:
                _LOGGER.info("Overwrote existing file: %s", file_path)
            else:
                _LOGGER.info("Created file: %s", file_path)
        except Exception as e:
            _LOGGER.error("Failed to write %s: %s", file_path, e)

    _LOGGER.info("Plant profile generated for '%s' at %s", plant_id, plant_dir)

    # Cache profile for future upload
    try:
        from .profile_upload_cache import cache_profile_for_upload

        cache_profile_for_upload(plant_id, hass)
    except Exception as exc:  # pragma: no cover - best effort cache
        _LOGGER.debug("Failed to cache profile %s: %s", plant_id, exc)

    return plant_id
