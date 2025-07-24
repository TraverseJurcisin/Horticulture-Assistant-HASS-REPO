import os
import json
import logging
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

def validate_profile_structure(plant_id: str, base_path: str = None, verbose: bool = False):
    """
    Validate the structure and content of a plant profile (set of JSON files) for a given plant_id.
    Checks each JSON file under plants/<plant_id>/ for expected keys and empty/null values.
    Logs any deviations from the expected profile template and returns a dictionary of issues.
    If run as a standalone script, outputs the summary to the console.

    :param plant_id: Identifier for the plant (name of the profile directory under base_path).
    :param base_path: Optional base directory for plant profiles (defaults to "plants" in current directory).
    :param verbose: If True, include more detailed output (e.g., log files that have no issues as "OK", list unexpected keys).
    :return: Dictionary of issues found. The keys are filenames and values are dictionaries describing issues:
             {"missing_keys": [...], "empty_fields": [...], "error": "..." (if any format errors), "extra_keys": [...]}.
    """
    # Determine base directory for plant profiles
    base_dir = Path(base_path) if base_path else Path(os.getcwd()) / "plants"
    plant_dir = base_dir / str(plant_id)
    issues = {}
    if not plant_dir.is_dir():
        _LOGGER.error("Plant directory not found: %s", plant_dir)
        return {}
    # Define expected keys for each known profile file
    expected_keys = {
        "general.json": {"plant_id", "display_name", "plant_type", "cultivar", "species", "location",
                         "lifecycle_stage", "auto_lifecycle_mode", "auto_approve_all", "tags",
                         "sensor_entities", "actuator_entities", "start_date"},
        "environment.json": {"light", "temperature", "humidity", "hardiness_zone", "EC", "pH"},
        "nutrition.json": {"leaf_nitrogen_ppm", "leaf_phosphorus_ppm", "leaf_potassium_ppm", "leaf_calcium_ppm",
                           "leaf_magnesium_ppm", "leaf_sulfur_ppm", "leaf_iron_ppm", "leaf_manganese_ppm",
                           "leaf_zinc_ppm", "leaf_copper_ppm", "leaf_boron_ppm", "leaf_molybdenum_ppm",
                           "leaf_chlorine_ppm", "leaf_arsenic_ppm", "leaf_cadmium_ppm", "leaf_lead_ppm",
                           "leaf_mercury_ppm", "leaf_nickel_ppm", "leaf_cobalt_ppm", "leaf_selenium_ppm"},
        "irrigation.json": {"soil_moisture_pct"},
        # stages.json has dynamic keys (stage names), will handle separately
        "soil_relationships.json": {"ph_range", "soil_ec_preference", "bulk_density", "cec_tolerance",
                                    "texture_class", "allelopathy", "root_soil_response", "media_suitability"},
        "microbiome.json": {"microbial_associations", "pathogenic_suppressors", "root_exudates",
                             "microbial_diversity_index", "co_cultured_species"},
        "introduction.json": {"primary_uses", "duration", "growth_habit", "key_features", "deciduous_or_evergreen",
                               "history", "native_regions", "domestication", "cultural_significance",
                               "legal_restrictions", "etymology", "cautions"},
        "identification.json": {"general_description", "leaf_structure", "adaptations", "rooting",
                                 "storm_resistance", "self_pruning", "growth_rates", "dimensions",
                                 "phylogeny", "defenses", "ecological_interactions"},
        "reproductive.json": {"pollination_type", "flowering_triggers", "fruit_development",
                               "harvest_readiness", "self_pruning", "flower_to_fruit_rate"},
        "phenology.json": {"flowering_period", "fruiting_period", "dormancy_triggers",
                            "stage_by_zone_estimates", "chill_hour_needs"},
        "genetics.json": {"gmo_status", "ploidy", "genetic_stability", "propagation_method", "genotyping_results",
                          "resistance_traits", "clade", "known_mutations", "commercial_protection"},
        "cultivar_lineage.json": {"parentage", "named_crosses", "hybridization_purpose", "ancestral_traits",
                                   "naming_origin", "divergence_from_wild", "related_commercial_varieties"},
        "regulatory.json": {"propagation_laws", "local_restrictions", "state_restrictions", "national_restrictions",
                             "seed_labeling_requirements", "intellectual_property_claims", "banned_substances",
                             "ethical_sourcing"},
        "export_profile.json": {"exportable_forms", "phytosanitary_certificates", "fumigation_status",
                                 "customs_codes", "known_trade_restrictions", "preferred_international_markets",
                                 "country_specific_demand"},
        "storage.json": {"shelf_life", "spoilage_conditions", "packaging_type", "storage_environment",
                         "stability_notes", "post_storage_QA"},
        "processing.json": {"postharvest_steps", "critical_control_points", "residue_breakdown",
                             "transformation_compounds", "value_added_processing_options",
                             "food_grade_standards", "pharmaceutical_standards"},
        "harvest.json": {"harvest_timing", "indicators_of_ripeness", "harvesting_method",
                         "postharvest_storage", "spoilage_rate", "market_channels"},
        "yield.json": {"expected_yield_range", "standard_yield_unit", "per_area_volume_metrics",
                       "historical_yield", "yield_density_range", "projected_yield_model"},
        "stage_progress.json": {"observed_stage", "expected_stage", "last_transition_date",
                                 "next_expected_stage", "growth_rate_class", "current_duration_days"},
        # calendar_timing.json has dynamic zone keys, handle separately
        "companion_plants.json": {"companion_species", "antagonists", "spatial_proximity_notes",
                                   "beneficial_biochemical_interactions", "known_competitive_exclusion_zones"},
        "rotation_guidance.json": {"rotation_families", "soil_impact", "antagonistic_residue_timing",
                                   "ideal_rotation_years", "soil_remediation_value", "successional_compatibility"},
        "biochemistry.json": {"flavor_aromatic_compounds", "medicinal_uses", "bioavailability",
                               "nutrient_density", "antioxidant_load", "toxin_profiles"},
        "metabolite_profile.json": {"cannabinoids", "alkaloids", "terpenes", "polyphenols",
                                    "enzymatic_inhibitors", "hormone_influencers", "biosynthetic_pathway_markers"},
        "climate_adaptability.json": {"high_temp_tolerance", "low_temp_tolerance", "photoperiod_sensitivity",
                                      "rainfall_tolerance", "radiation_tolerance", "heat_unit_accumulation",
                                      "overwintering_behavior"},
        "zone_suitability.json": {"USDA_zones", "Köppen_climates", "optimal_latitude_band",
                                   "global_elevation_band", "subtropical_to_temperate_gradient", "known_zone_failures"}
    }
    # Define expected nested subkeys for specific fields within files
    expected_nested_keys = {
        "reproductive.json": {"flowering_triggers": {"temperature", "photoperiod", "nutrient"}},
        "storage.json": {"storage_environment": {"temperature", "relative_humidity", "airflow", "darkness"}},
        "yield.json": {"per_area_volume_metrics": {"per_acre", "per_cubic_ft", "per_gallon_media"}}
    }
    # List all JSON files in the plant directory
    for file_path in plant_dir.glob("*.json"):
        file_name = file_path.name
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except Exception as e:
            _LOGGER.error("Failed to read/parse JSON file %s: %s", file_path, e)
            issues[file_name] = {"error": f"JSON parse error: {e}"}
            continue
        if not isinstance(content, dict):
            _LOGGER.warning("Profile file %s is not a JSON object (dict).", file_path)
            issues[file_name] = {"error": "Content is not a dict"}
            continue
        # Determine expected keys for this file if known
        expected = expected_keys.get(file_name)
        missing_keys = []
        extra_keys = []
        if expected is not None:
            # If 'start_date' is optional and not present, remove it from expected to avoid flagging as missing
            if file_name == "general.json" and "start_date" not in content:
                expected = expected.copy()
                expected.discard("start_date")
            missing_keys = sorted(list(expected - set(content.keys())))
            extra = set(content.keys()) - expected
            extra_keys = sorted(list(extra)) if extra else []
        else:
            missing_keys = []
            extra_keys = []
        # Check nested structural keys if this file has expected nested structures
        nested_issues = []
        if file_name == "stages.json":
            # Validate each stage entry in stages file
            for stage_name, stage_data in content.items():
                if not isinstance(stage_data, dict):
                    _LOGGER.warning("Stage '%s' in %s is not a dictionary.", stage_name, file_path)
                    nested_issues.append(f"Stage {stage_name}: not a dict")
                else:
                    if "stage_duration" not in stage_data:
                        nested_issues.append(f"Stage {stage_name}: missing 'stage_duration'")
                        _LOGGER.info("Stage '%s' in %s missing key 'stage_duration'.", stage_name, file_path)
                    if "notes" not in stage_data:
                        nested_issues.append(f"Stage {stage_name}: missing 'notes'")
                        _LOGGER.info("Stage '%s' in %s missing key 'notes'.", stage_name, file_path)
        elif file_name == "calendar_timing.json":
            # Validate each zone entry in calendar timing file
            for zone, timing in content.items():
                if not isinstance(timing, dict):
                    _LOGGER.warning("Calendar timing entry '%s' in %s is not a dictionary.", zone, file_path)
                    nested_issues.append(f"Zone {zone}: not a dict")
                else:
                    for required_stage in ["seedling", "veg", "flower"]:
                        if required_stage not in timing:
                            nested_issues.append(f"Zone {zone}: missing '{required_stage}'")
                            _LOGGER.info("Zone '%s' in %s missing key '%s'.", zone, file_path, required_stage)
        else:
            if file_name in expected_nested_keys:
                for parent_key, subkeys in expected_nested_keys[file_name].items():
                    if parent_key in content and isinstance(content[parent_key], dict):
                        for subkey in subkeys:
                            if subkey not in content[parent_key]:
                                nested_issues.append(f"{parent_key}.{subkey} (missing)")
                                _LOGGER.info("File %s missing nested key '%s' in '%s'.", file_path, subkey, parent_key)
                    if parent_key in content and not isinstance(content[parent_key], dict):
                        _LOGGER.warning("In file %s, expected %s to be a dict, found %s.", file_path, parent_key, type(content[parent_key]).__name__)
                        nested_issues.append(f"{parent_key} is not a dict")
                    # If parent key is missing entirely, that is covered by missing_keys above
        # Identify empty or null fields (including placeholders like "TBD")
        empty_fields = []
        for key, value in content.items():
            if isinstance(value, bool):
                # don't treat booleans as empty (False is a valid value)
                pass
            elif value is None:
                empty_fields.append(key)
            elif isinstance(value, str):
                if value.strip() == "" or value.strip().lower() == "tbd":
                    empty_fields.append(key)
            elif isinstance(value, (list, tuple, set)):
                if len(value) == 0:
                    empty_fields.append(key)
            elif isinstance(value, dict):
                if len(value) == 0:
                    empty_fields.append(key)
                else:
                    for subkey, subval in value.items():
                        if subval is None:
                            empty_fields.append(f"{key}.{subkey}")
                        elif isinstance(subval, str):
                            if subval.strip() == "" or subval.strip().lower() == "tbd":
                                empty_fields.append(f"{key}.{subkey}")
                        elif isinstance(subval, (list, tuple, set)):
                            if len(subval) == 0:
                                empty_fields.append(f"{key}.{subkey}")
                        elif isinstance(subval, dict):
                            if len(subval) == 0:
                                empty_fields.append(f"{key}.{subkey}")
        empty_fields = sorted(set(empty_fields))
        # Log and record issues for this file
        file_issues = {}
        if missing_keys:
            file_issues["missing_keys"] = missing_keys
            _LOGGER.info("%s missing keys: %s", file_name, ", ".join(missing_keys))
        if nested_issues:
            file_issues["nested_issues"] = nested_issues
            _LOGGER.info("%s structure issues: %s", file_name, "; ".join(nested_issues))
        if empty_fields:
            file_issues["empty_fields"] = empty_fields
            _LOGGER.info("%s empty/null fields: %s", file_name, ", ".join(empty_fields))
        if extra_keys:
            file_issues["extra_keys"] = extra_keys
            if verbose:
                _LOGGER.info("%s unexpected keys: %s", file_name, ", ".join(extra_keys))
        if not file_issues:
            if verbose:
                _LOGGER.info("%s: OK", file_name)
        else:
            issues[file_name] = file_issues
    # Summary log per profile
    if issues:
        _LOGGER.info("Summary of profile issues for '%s': %d file(s) with problems.", plant_id, len(issues))
    else:
        _LOGGER.info("All profile files for '%s' passed validation with no issues.", plant_id)
    return issues

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Validate the structure of plant profile JSON files.")
    parser.add_argument("plant_id", help="Plant ID (profile directory name) to validate")
    parser.add_argument("--base-path", dest="base_path", help="Base directory containing plant profiles (defaults to ./plants)")
    parser.add_argument("-v", "--verbose", action="store_true", dest="verbose", help="Verbose output")
    args = parser.parse_args()
    # Configure basic logging to console
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # Check plant directory existence before validation
    base_dir = Path(args.base_path) if args.base_path else Path(os.getcwd()) / "plants"
    plant_dir = base_dir / str(args.plant_id)
    if not plant_dir.is_dir():
        print(f"Error: Plant directory not found at {plant_dir}")
    else:
        result = validate_profile_structure(args.plant_id, base_path=args.base_path, verbose=args.verbose)
        # Print summary to console
        if not result:
            print(f"No issues found for plant profile '{args.plant_id}'.")
        else:
            print(f"Issues found in plant profile '{args.plant_id}':")
            for fname, issue_data in result.items():
                issue_list = []
                if "error" in issue_data:
                    issue_list.append(f"ERROR: {issue_data['error']}")
                if "missing_keys" in issue_data:
                    issue_list.append(f"Missing keys: {', '.join(issue_data['missing_keys'])}")
                if "nested_issues" in issue_data:
                    issue_list.append(f"Nested structure issues: {'; '.join(issue_data['nested_issues'])}")
                if "empty_fields" in issue_data:
                    issue_list.append(f"Empty/null fields: {', '.join(issue_data['empty_fields'])}")
                if "extra_keys" in issue_data:
                    issue_list.append(f"Unexpected keys: {', '.join(issue_data['extra_keys'])}")
                issues_summary = "; ".join(issue_list)
                print(f" - {fname}: {issues_summary}")
