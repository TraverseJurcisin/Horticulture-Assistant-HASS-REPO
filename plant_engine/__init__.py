"""Plant engine package utilities."""

from .utils import load_json, save_json
from .environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
    optimize_environment,
    calculate_environment_metrics,
    calculate_absolute_humidity,
    get_target_dli,
    get_target_vpd,
    photoperiod_for_target_dli,
    calculate_dli,
    calculate_dli_series,
    humidity_for_target_vpd,
    recommend_photoperiod,
    EnvironmentMetrics,
    EnvironmentOptimization,
    list_supported_plants as list_environment_plants,
)
from .pest_manager import (
    get_pest_guidelines,
    recommend_treatments as recommend_pest_treatments,
    list_supported_plants as list_pest_plants,
)
from .pest_monitor import (
    get_pest_thresholds,
    assess_pest_pressure,
    recommend_threshold_actions,
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
)
from .rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
    get_soil_parameters,
    RootZone,
)
from .irrigation_manager import (
    recommend_irrigation_volume,
    recommend_irrigation_interval,
    list_supported_plants as list_irrigation_plants,
    get_daily_irrigation_target,
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
from .guidelines import get_guideline_summary
from .report import DailyReport
from .engine import load_profile
from .health_report import generate_health_report
from .deficiency_manager import (
    get_deficiency_treatment,
    recommend_deficiency_treatments,
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
)
from .yield_prediction import (
    list_supported_plants as list_yield_plants,
    get_estimated_yield,
    estimate_remaining_yield,
)
from .pruning_manager import (
    list_supported_plants as list_pruning_plants,
    list_stages as list_pruning_stages,
    get_pruning_instructions,
)
from .nutrient_analysis import analyze_nutrient_profile
from .water_quality import (
    list_analytes as list_water_analytes,
    get_threshold as get_water_threshold,
    interpret_water_profile,
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
from .thermal_time import (
    calculate_gdd,
    list_supported_plants as list_gdd_plants,
    get_stage_gdd_requirement,
    predict_stage_completion,
    accumulate_gdd_series,
)
from .compute_transpiration import TranspirationMetrics

# Run functions should be imported explicitly to avoid heavy imports at package
# initialization time.
__all__ = [
    "load_json",
    "save_json",
    "get_environmental_targets",
    "recommend_environment_adjustments",
    "optimize_environment",
    "calculate_environment_metrics",
    "calculate_absolute_humidity",
    "get_target_dli",
    "get_target_vpd",
    "photoperiod_for_target_dli",
    "calculate_dli",
    "calculate_dli_series",
    "humidity_for_target_vpd",
    "recommend_photoperiod",
    "EnvironmentMetrics",
    "EnvironmentOptimization",
    "list_environment_plants",
    "get_pest_guidelines",
    "recommend_pest_treatments",
    "list_pest_plants",
    "get_pest_thresholds",
    "assess_pest_pressure",
    "recommend_threshold_actions",
    "get_disease_guidelines",
    "recommend_disease_treatments",
    "get_disease_prevention",
    "recommend_disease_prevention",
    "list_disease_plants",
    "recommend_fertigation_schedule",
    "recommend_correction_schedule",
    "get_fertilizer_purity",
    "recommend_nutrient_mix_with_cost_breakdown",
    "calculate_deficiencies",
    "calculate_micro_deficiencies",
    "get_deficiency_treatment",
    "recommend_deficiency_treatments",
    "list_surplus_nutrients",
    "get_surplus_action",
    "recommend_surplus_actions",
    "list_nutrient_plants",
    "list_micro_plants",
    "get_micro_levels",
    "get_stage_info",
    "list_growth_stages",
    "estimate_rootzone_depth",
    "estimate_water_capacity",
    "get_soil_parameters",
    "RootZone",
    "recommend_irrigation_volume",
    "recommend_irrigation_interval",
    "list_irrigation_plants",
    "get_daily_irrigation_target",
    "HarvestRecord",
    "load_yield_history",
    "record_harvest",
    "get_total_yield",
    "list_yield_plants",
    "get_estimated_yield",
    "estimate_remaining_yield",
    "generate_health_report",
    "list_water_analytes",
    "get_water_threshold",
    "interpret_water_profile",
    "list_ph_plants",
    "get_ph_range",
    "recommend_ph_adjustment",
    "estimate_ph_adjustment_volume",
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
    "list_toxicity_plants",
    "get_toxicity_thresholds",
    "check_toxicities",
    "get_guideline_summary",
    "DailyReport",
    "load_profile",
    "TranspirationMetrics",
]
