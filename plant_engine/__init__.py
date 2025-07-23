"""Plant engine package utilities."""

from .utils import load_json, save_json
from .datasets import list_datasets, get_dataset_description
from .environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
    optimize_environment,
    calculate_environment_metrics,
    calculate_absolute_humidity,
    get_target_dli,
    get_target_vpd,
    get_target_photoperiod,
    photoperiod_for_target_dli,
    calculate_dli,
    calculate_dli_series,
    humidity_for_target_vpd,
    get_target_co2,
    calculate_co2_injection,
    recommend_co2_injection,
    get_co2_price,
    estimate_co2_cost,
    recommend_co2_injection_with_cost,
    CO2_MG_PER_M3_PER_PPM,
    get_humidity_action,
    recommend_humidity_action,
    recommend_photoperiod,
    EnvironmentMetrics,
    EnvironmentOptimization,
    StressFlags,
    evaluate_wind_stress,
    evaluate_stress_conditions,
    list_supported_plants as list_environment_plants,
)
from .pest_manager import (
    get_pest_guidelines,
    recommend_treatments as recommend_pest_treatments,
    list_supported_plants as list_pest_plants,
    get_pest_prevention,
    recommend_prevention as recommend_pest_prevention,
)
from .pest_monitor import (
    get_pest_thresholds,
    assess_pest_pressure,
    recommend_threshold_actions,
)
from .disease_monitor import (
    get_disease_thresholds,
    assess_disease_pressure,
    classify_disease_severity,
    recommend_threshold_actions as recommend_disease_threshold_actions,
    generate_disease_report,
)
from .disease_manager import (
    get_disease_guidelines,
    recommend_treatments as recommend_disease_treatments,
    list_supported_plants as list_disease_plants,
    get_disease_prevention,
    recommend_prevention as recommend_disease_prevention,
)
from .fertigation import (
    recommend_fertigation_schedule,
    recommend_correction_schedule,
    get_fertilizer_purity,
    recommend_nutrient_mix_with_cost_breakdown,
    generate_fertigation_plan,
    calculate_mix_nutrients,
    estimate_stage_cost,
    estimate_cycle_cost,
    generate_cycle_fertigation_plan,
    generate_cycle_fertigation_plan_with_cost,
)
from .rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
    get_soil_parameters,
    get_infiltration_rate,
    estimate_infiltration_time,
    RootZone,
)
from .soil_manager import (
    list_supported_plants as list_soil_plants,
    get_soil_targets,
    calculate_soil_deficiencies,
    calculate_soil_surplus,
    score_soil_nutrients,
)
from .irrigation_manager import (
    recommend_irrigation_volume,
    recommend_irrigation_interval,
    list_supported_plants as list_irrigation_plants,
    get_daily_irrigation_target,
    generate_irrigation_schedule,
)
from .nutrient_manager import (
    calculate_deficiencies,
    calculate_all_surplus,
    list_supported_plants as list_nutrient_plants,
)
from .micro_manager import (
    list_supported_plants as list_micro_plants,
    get_recommended_levels as get_micro_levels,
    calculate_deficiencies as calculate_micro_deficiencies,
    calculate_surplus as calculate_micro_surplus,
)
from .growth_stage import get_stage_info, list_growth_stages
from .harvest_planner import build_stage_schedule
from .guidelines import get_guideline_summary
from .report import DailyReport
from .engine import load_profile
from .health_report import generate_health_report
from .deficiency_manager import (
    get_deficiency_treatment,
    recommend_deficiency_treatments,
    diagnose_deficiency_actions,
)
from .surplus_manager import (
    list_known_nutrients as list_surplus_nutrients,
    get_surplus_action,
    recommend_surplus_actions,
)
from .yield_manager import (
    HarvestRecord,
    load_yield_history,
    record_harvest,
    get_total_yield,
    get_total_nutrient_removal,
)
from .yield_prediction import (
    list_supported_plants as list_yield_plants,
    get_estimated_yield,
    estimate_remaining_yield,
)
from .constants import get_stage_multiplier, STAGE_MULTIPLIERS, DEFAULT_ENV
from .pruning_manager import (
    list_supported_plants as list_pruning_plants,
    list_stages as list_pruning_stages,
    get_pruning_instructions,
)
from .nutrient_analysis import analyze_nutrient_profile
from .nutrient_leaching import (
    list_known_nutrients as list_leaching_nutrients,
    get_leaching_rate,
    estimate_leaching_loss,
    compensate_for_leaching,
)
from .water_quality import (
    list_analytes as list_water_analytes,
    get_threshold as get_water_threshold,
    interpret_water_profile,
)
from .ec_manager import (
    list_supported_plants as list_ec_plants,
    get_ec_range,
    classify_ec_level,
    recommend_ec_adjustment,
)
from .water_usage import (
    list_supported_plants as list_water_use_plants,
    get_daily_use as get_daily_water_use,
)
from .toxicity_manager import (
    list_supported_plants as list_toxicity_plants,
    get_toxicity_thresholds,
    check_toxicities,
)
from .ph_manager import (
    list_supported_plants as list_ph_plants,
    get_ph_range,
    recommend_ph_adjustment,
    estimate_ph_adjustment_volume,
)
from .light_spectrum import (
    list_supported_plants as list_spectrum_plants,
    get_spectrum as get_light_spectrum,
    get_red_blue_ratio,
)
from .thermal_time import (
    calculate_gdd,
    list_supported_plants as list_gdd_plants,
    get_stage_gdd_requirement,
    predict_stage_completion,
    accumulate_gdd_series,
)
from .nutrient_budget import (
    list_supported_plants as list_budget_plants,
    get_removal_rates,
    estimate_total_removal,
    estimate_required_nutrients,
)
from .compute_transpiration import TranspirationMetrics

# Run functions should be imported explicitly to avoid heavy imports at package
# initialization time.
__all__ = [
    "load_json",
    "save_json",
    "list_datasets",
    "get_dataset_description",
    "get_environmental_targets",
    "recommend_environment_adjustments",
    "optimize_environment",
    "calculate_environment_metrics",
    "calculate_absolute_humidity",
    "get_target_dli",
    "get_target_vpd",
    "get_target_photoperiod",
    "photoperiod_for_target_dli",
    "calculate_dli",
    "calculate_dli_series",
    "get_target_co2",
    "calculate_co2_injection",
    "recommend_co2_injection",
    "get_co2_price",
    "estimate_co2_cost",
    "recommend_co2_injection_with_cost",
    "CO2_MG_PER_M3_PER_PPM",
    "humidity_for_target_vpd",
    "get_humidity_action",
    "recommend_humidity_action",
    "recommend_photoperiod",
    "EnvironmentMetrics",
    "EnvironmentOptimization",
    "StressFlags",
    "evaluate_wind_stress",
    "evaluate_stress_conditions",
    "list_environment_plants",
    "get_pest_guidelines",
    "recommend_pest_treatments",
    "get_pest_prevention",
    "recommend_pest_prevention",
    "list_pest_plants",
    "get_pest_thresholds",
    "assess_pest_pressure",
    "recommend_threshold_actions",
    "get_disease_guidelines",
    "recommend_disease_treatments",
    "get_disease_prevention",
    "recommend_disease_prevention",
    "list_disease_plants",
    "get_disease_thresholds",
    "assess_disease_pressure",
    "classify_disease_severity",
    "recommend_disease_threshold_actions",
    "generate_disease_report",
    "recommend_fertigation_schedule",
    "recommend_correction_schedule",
    "get_fertilizer_purity",
    "recommend_nutrient_mix_with_cost_breakdown",
    "generate_fertigation_plan",
    "calculate_mix_nutrients",
    "estimate_stage_cost",
    "estimate_cycle_cost",
    "generate_cycle_fertigation_plan",
    "generate_cycle_fertigation_plan_with_cost",
    "calculate_deficiencies",
    "calculate_micro_deficiencies",
    "get_deficiency_treatment",
    "recommend_deficiency_treatments",
    "diagnose_deficiency_actions",
    "list_surplus_nutrients",
    "get_surplus_action",
    "recommend_surplus_actions",
    "list_nutrient_plants",
    "get_nutrient_weight",
    "score_nutrient_levels",
    "list_micro_plants",
    "get_micro_levels",
    "get_stage_info",
    "list_growth_stages",
    "build_stage_schedule",
    "estimate_rootzone_depth",
    "estimate_water_capacity",
    "get_soil_parameters",
    "get_infiltration_rate",
    "estimate_infiltration_time",
    "RootZone",
    "list_soil_plants",
    "get_soil_targets",
    "calculate_soil_deficiencies",
    "calculate_soil_surplus",
    "score_soil_nutrients",
    "recommend_irrigation_volume",
    "recommend_irrigation_interval",
    "list_irrigation_plants",
    "get_daily_irrigation_target",
    "generate_irrigation_schedule",
    "HarvestRecord",
    "load_yield_history",
    "record_harvest",
    "get_total_yield",
    "get_total_nutrient_removal",
    "list_yield_plants",
    "get_estimated_yield",
    "estimate_remaining_yield",
    "list_budget_plants",
    "get_removal_rates",
    "estimate_total_removal",
    "estimate_required_nutrients",
    "generate_health_report",
    "list_water_analytes",
    "get_water_threshold",
    "interpret_water_profile",
    "list_ec_plants",
    "get_ec_range",
    "classify_ec_level",
    "recommend_ec_adjustment",
    "list_water_use_plants",
    "get_daily_water_use",
    "list_ph_plants",
    "get_ph_range",
    "recommend_ph_adjustment",
    "estimate_ph_adjustment_volume",
    "list_spectrum_plants",
    "get_light_spectrum",
    "get_red_blue_ratio",
    "list_pruning_plants",
    "list_pruning_stages",
    "get_pruning_instructions",
    "calculate_gdd",
    "list_gdd_plants",
    "get_stage_gdd_requirement",
    "predict_stage_completion",
    "accumulate_gdd_series",
    "calculate_all_surplus",
    "calculate_micro_surplus",
    "analyze_nutrient_profile",
    "list_leaching_nutrients",
    "get_leaching_rate",
    "estimate_leaching_loss",
    "compensate_for_leaching",
    "list_toxicity_plants",
    "get_toxicity_thresholds",
    "check_toxicities",
    "get_guideline_summary",
    "DailyReport",
    "load_profile",
    "TranspirationMetrics",
    "STAGE_MULTIPLIERS",
    "get_stage_multiplier",
    "DEFAULT_ENV",
]
