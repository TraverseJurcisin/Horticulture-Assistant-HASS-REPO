"""Plant engine package utilities."""

from .utils import load_json, save_json
from .environment_manager import (
    get_environmental_targets,
    recommend_environment_adjustments,
    optimize_environment,
    calculate_environment_metrics,
    humidity_for_target_vpd,
    EnvironmentMetrics,
    EnvironmentOptimization,
    calculate_gdd,
    gdd_for_plant,
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
)
from .fertigation import (
    recommend_fertigation_schedule,
    recommend_correction_schedule,
    get_fertilizer_purity,
)
from .rootzone_model import (
    estimate_rootzone_depth,
    estimate_water_capacity,
    RootZone,
)
from .irrigation_manager import (
    recommend_irrigation_volume,
    recommend_irrigation_interval,
)
from .nutrient_manager import (
    calculate_deficiencies,
    list_supported_plants as list_nutrient_plants,
)
from .growth_stage import get_stage_info, list_growth_stages
from .health_report import generate_health_report
from .yield_manager import (
    HarvestRecord,
    load_yield_history,
    record_harvest,
    get_total_yield,
)
from .water_quality import (
    list_analytes as list_water_analytes,
    get_threshold as get_water_threshold,
    interpret_water_profile,
)
from .ph_manager import (
    list_supported_plants as list_ph_plants,
    get_ph_range,
    recommend_ph_adjustment,
)
from .compute_transpiration import TranspirationMetrics

# Run functions should be imported explicitly to avoid heavy imports at package
# initialization time.
__all__ = [
    "assess_pest_pressure",
    "calculate_deficiencies",
    "calculate_environment_metrics",
    "calculate_gdd",
    "EnvironmentMetrics",
    "EnvironmentOptimization",
    "estimate_rootzone_depth",
    "estimate_water_capacity",
    "gdd_for_plant",
    "generate_health_report",
    "get_disease_guidelines",
    "get_environmental_targets",
    "get_fertilizer_purity",
    "get_pest_guidelines",
    "get_pest_thresholds",
    "get_ph_range",
    "get_stage_info",
    "get_total_yield",
    "get_water_threshold",
    "HarvestRecord",
    "humidity_for_target_vpd",
    "interpret_water_profile",
    "list_disease_plants",
    "list_environment_plants",
    "list_growth_stages",
    "list_nutrient_plants",
    "list_pest_plants",
    "list_ph_plants",
    "list_water_analytes",
    "load_json",
    "load_yield_history",
    "optimize_environment",
    "recommend_correction_schedule",
    "recommend_disease_treatments",
    "recommend_environment_adjustments",
    "recommend_fertigation_schedule",
    "recommend_irrigation_interval",
    "recommend_irrigation_volume",
    "recommend_pest_treatments",
    "recommend_ph_adjustment",
    "recommend_threshold_actions",
    "record_harvest",
    "RootZone",
    "save_json",
    "TranspirationMetrics",
]
