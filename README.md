# Horticulture Assistant

Horticulture Assistant brings per-plant automation and monitoring to Home Assistant. It exposes a suite of sensors, switches and scripts that allow you to manage irrigation, nutrients and general plant health from one place.

---

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Installation](#installation)
  - [HACS](#hacs)
  - [Manual](#manual)
- [Quick Start](#quick-start)
- [Plant Profile Format](#plant-profile-format)
- [Plant Registry](#plant-registry)
- [Repository Structure](#repository-structure)
- [Data Files](#data-files)
- [Advanced Topics](#advanced-topics)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Command Line Utilities](#command-line-utilities)
- [Running Tests](#running-tests)
- [References](#references)
- [License](#license)

---

## Overview
This integration is under active development and currently distributed as a
private custom repository. It collects environmental data, computes nutrient
recommendations and can optionally leverage AI models to refine your crop
schedule. The goal is full hands‑off operation with the ability to review and
approve changes from Home Assistant.

### Safety & Disclaimer
The bundled datasets are not exhaustive and may contain inaccuracies. Always
cross‑check any nutrient or treatment advice with a local agronomist before
applying it to your plants.

## Features
### Plant Monitoring
- Moisture, EC and nutrient level sensors
- Environmental metrics including light and CO₂
- Binary sensors for irrigation readiness

### Automation & AI
- Dynamic thresholds based on growth stage history
- Optional OpenAI or offline models for nutrient planning
- Irrigation and fertigation switches with approval queues

### Data & Analytics
- Disease and pest treatment recommendations
- Environment optimization suggestions with pH guidance
- Precise pH adjustment volume calculations for nutrient solutions
- Heat stress warnings using heat index thresholds
- Humidity stress warnings when humidity is outside safe ranges
- Light stress detection using DLI ranges
- Stage-adjusted nutrient targets
- Leaf tissue analysis with nutrient balance scoring
- Nutrient deficiency severity and treatment recommendations
- Combined deficiency/toxicity nutrient status classification
- Automated deficiency action recommendations in daily reports
- Example crop profiles for strawberries, basil, spinach and more
- Helper functions to list known pests and diseases by crop

---

## Installation
### HACS
1. Open HACS in Home Assistant and navigate to **Integrations → Custom Repositories**.
2. Add this repository URL and install **Horticulture Assistant** from the list.
3. Restart Home Assistant when prompted.

### Manual
1. Clone this repository.
2. Copy `custom_components/horticulture_assistant/` into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

---

## Quick Start
1. Go to **Settings → Devices & Services** in Home Assistant.
2. Choose **Add Integration** and search for **Horticulture Assistant**.
3. Follow the prompts to link sensors and select or create plant profiles.
4. Copy `blueprints/automation/plant_monitoring.yaml` into `<config>/blueprints/automation/>` and create an automation from it.
5. Optionally enable `input_boolean.auto_approve_all` to automatically apply AI recommendations.
6. Ensure all numeric sensors use `state_class: measurement` so statistics are recorded.

Plant profiles are JSON files in the `plants/` folder, and can be created through the built-in config flow or edited manually.

## Plant Profile Format
Each plant is defined in JSON. A minimal example:

```json
{
  "name": "Strawberry",
  "stages": {
    "vegetative": {
      "target_ec": 1.6,
      "target_vpd": [0.8, 1.2],
      "photoperiod": 18
    }
  }
}
```

Place profiles under the `plants/` directory. They can be referenced during setup or selected through the config flow.

## Plant Registry
Multiple plant profiles can be indexed in `plant_registry.json` so automations can discover them easily. Example:

```json
{
  "citrus_backyard_spring2025": {
    "display_name": "Backyard Citrus Spring 2025",
    "plant_type": "citrus",
    "current_lifecycle_stage": "fruiting",
    "tags": ["citrus", "meyer_lemon", "backyard"]
  }
}
```
Tags defined in `tags.json` allow you to group plants for dashboards and analytics.


---

## Repository Structure
```text
horticulture-assistant/
├── custom_components/horticulture_assistant/  # core integration code
├── blueprints/                                # automation blueprints
├── data/                                      # reference datasets
├── plant_engine/                              # nutrient and disease modules
│   └── constants.py                           # shared constants
├── scripts/                                   # helper scripts
├── plants/                                    # example plant profiles
├── plant_registry.json
├── tags.json
└── tests/                                     # unit tests
```

Additional data files include `product_database.json` and `wsda_fertilizer_database.json` for fertilizer lookups.

## Data Files
Key reference datasets reside in the `data/` directory:
- `environment_guidelines.json` – optimal temperature, humidity and light by crop
- `nutrient_guidelines.json` – recommended N‑P‑K levels across stages
- `micronutrient_guidelines.json` – Fe/Mn/Zn/B/Cu/Mo levels across stages
- `disease_guidelines.json` and `pest_guidelines.json` – treatment references
- `disease_prevention.json` – cultural practices to prevent common diseases
- `pest_thresholds.json` – action thresholds for common pests
- `beneficial_insects.json` – natural predator recommendations for pests
- `pest_prevention.json` – cultural practices to deter common pests
- `bioinoculant_guidelines.json` – microbial inoculant suggestions by crop
- `pest_monitoring_intervals.json` – recommended scouting frequency by stage
- `ipm_guidelines.json` – integrated pest management practices by crop
- `water_quality_thresholds.json` – acceptable ion limits for irrigation water
- `water_quality_actions.json` – recommended treatments when limits are exceeded
- `fertilizer_purity.json` – default purity factors for common fertilizers
- `fertilizer_solubility.json` – maximum solubility (g/L) for fertilizers
- `fertigation_recipes.json` – grams per liter of each product for standard mixes
- `light_spectrum_guidelines.json` – optimal red/blue light ratios by stage
- `nutrient_uptake.json` – typical daily N‑P‑K demand per plant stage
- `nutrient_tag_modifiers.json` – per-tag multipliers for nutrient scheduling
- `heat_stress_thresholds.json` – heat index limits used for stress warnings
- `cold_stress_thresholds.json` – minimum temperature limits for cold stress
- `humidity_actions.json` – actions to correct low or high humidity levels
- `wind_stress_thresholds.json` – maximum safe wind speed before damage
- `climate_zone_guidelines.json` – temperature and humidity ranges by climate zone
- `nutrient_deficiency_treatments.json` – remedies for common nutrient shortages
- `nutrient_surplus_actions.json` – steps to mitigate excess nutrient levels
- `nutrient_interactions.json` – warning ratios for antagonistic nutrients
- `nutrient_toxicity_thresholds.json` – upper limits to flag potential toxicity
- `photoperiod_guidelines.json` – recommended day length by crop stage
- `nutrient_toxicity_symptoms.json` – visual cues indicating nutrient excess
- `nutrient_toxicity_treatments.json` – suggested mitigation steps for toxicity
- `growth_medium_ph_ranges.json` – preferred pH ranges for soil, coco and hydroponics
- `ph_adjustment_factors.json` – acid/base effect per mL for pH correction
- `growth_stages.json` – lifecycle stage durations and notes by crop
- `stage_multipliers.json` – default nutrient scaling factors by stage
- `pruning_guidelines.json` – stage-specific pruning recommendations
- `pruning_intervals.json` – days between recommended pruning events
- `soil_texture_parameters.json` – default field capacity and MAD values by soil texture
- `root_depth_guidelines.json` – typical maximum root depth (cm) for common crops
- `soil_nutrient_guidelines.json` – baseline soil N‑P‑K targets by crop
- `irrigation_guidelines.json` – default daily irrigation volume per plant stage
- `water_usage_guidelines.json` – estimated daily water use by crop stage
- `irrigation_efficiency.json` – efficiency factors for common irrigation methods
- `emitter_flow_rates.json` – typical emitter flow rates (L/h) for irrigation time estimates
- `hvac_energy_coefficients.json` – kWh usage per degree-day for heating and cooling
- `foliar_feed_guidelines.json` – recommended nutrient ppm for foliar sprays
- `foliar_feed_intervals.json` – suggested days between foliar applications
- `nutrient_leaching_rates.json` – estimated fraction of nutrients lost to leaching
- `yield/` – per‑plant yield logs created during operation
- `plant_density_guidelines.json` – recommended plant spacing (cm) for density calculations
- `pesticide_withdrawal_days.json` – required wait time before harvest after pesticide use
- `organic_pest_controls.json` – organic treatment options for common pests
- `wsda_fertilizer_database.json` – full fertilizer analysis database used by
  `plant_engine.wsda_lookup` for product N‑P‑K values
- `products_index.jsonl` – compact summary of WSDA products for fast searches (use `wsda_product_index`)
- `dataset_catalog.json` – short descriptions of the bundled datasets for quick reference
  Use `plant_engine.datasets.list_datasets()` to list available files and
  `get_dataset_description()` to read these summaries programmatically.

All dataset lookups are case-insensitive and ignore spaces thanks to the
`normalize_key` helper, so references such as `"Citrus"` and `"citrus"` map to
the same entries.

You can override the default `data/` directory by setting the environment
variable `HORTICULTURE_DATA_DIR` when running scripts or tests. An additional
`HORTICULTURE_OVERLAY_DIR` may contain files that override or extend those
datasets without copying the entire directory. Overlay files are merged
recursively so nested keys can be customized without redefining the entire
structure.
Multiple extra dataset directories can also be specified via
`HORTICULTURE_EXTRA_DATA_DIRS` as a list separated by your OS path separator
(``:`` on Linux/macOS, ``;`` on Windows). These paths are merged in the order
provided before any overlay files.
Call `plant_engine.utils.clear_dataset_cache()` if you modify these
environment variables while the application is running so changes are
immediately reflected.

The datasets are snapshots compiled from public resources. They may be outdated
or incomplete and should only be used as a starting point for your own research.


---

## Advanced Topics
- **YAML Automations**: Use the blueprints in `blueprints/automation/` for easy setup.
- **Custom Plant Profiles**: Drop JSON profiles in `plants/` for per‑plant settings.
- **Auto Approval**: Toggle `input_boolean.auto_approve_all` to apply AI recommendations automatically.
- **Data Logging**: Set `state_class: measurement` on sensors for proper history recording.
- **Customization**: Edit `plant_engine/constants.py` to tweak default environment
  readings or nutrient multipliers when profiles omit them.
- **Dataset Cache**: Call `plant_engine.utils.clear_dataset_cache()` after
  adjusting dataset environment variables to refresh cached lookups.
- **Dynamic Tags**: Tag plants (e.g. `"blueberry"`, `"fruiting"`) to generate grouped dashboards.
- **Nutrient Mix Helper**: The `recommend_nutrient_mix` function computes exact
  fertilizer grams needed to hit N/P/K targets and can optionally include
  micronutrients using the new `micronutrient_guidelines.json` dataset.
- **Mix Cost Estimation**: `recommend_nutrient_mix_with_cost` returns the same
  schedule along with an estimated dollar cost based on fertilizer prices.
- **Per-Plant Cost**: `estimate_mix_cost_per_plant` divides the total mix cost
  by plant count for precise budgeting.
- **Cost Per Liter**: `estimate_mix_cost_per_liter` helps compare fertilizer
  schedules by normalizing cost to the total solution volume.
- **Mix Nutrient Totals**: `calculate_mix_nutrients` reports the elemental
  nutrient amounts contributed by each fertilizer mix in milligrams.
- **Solution Weight Estimate**: `estimate_solution_mass` adds fertilizer mass to
  water volume to approximate the total weight of a nutrient solution.
- **Solubility Check**: `check_solubility_limits` warns when a fertilizer mix
  exceeds the maximum grams per liter defined in `fertilizer_solubility.json`.
- **Daily Uptake Estimation**: Use `estimate_daily_nutrient_uptake` to convert
  ppm guidelines and irrigation volume into milligrams of nutrients consumed
  each day.
- **Total Uptake Estimation**: `estimate_stage_totals` multiplies daily uptake by
  growth stage duration while `estimate_total_uptake` sums these values across
  the entire crop cycle.
- **Uptake Cost Estimation**: `estimate_stage_cost` and `estimate_cycle_cost`
  convert those totals into fertilizer costs using price data.
- **Irrigation Targets**: `get_daily_irrigation_target` returns default
  milliliters per plant based on `irrigation_guidelines.json`. The `get_daily_water_use` helper provides similar estimates from `water_usage_guidelines.json`.
- **Irrigation Efficiency**: `adjust_irrigation_for_efficiency` scales volumes
  based on delivery method using `irrigation_efficiency.json`.
- **Irrigation Duration Estimate**: `estimate_irrigation_time` uses `emitter_flow_rates.json` to predict how long a watering event will take.
- **Irrigation Schedule Efficiency**: `generate_irrigation_schedule` accepts a
  `method` parameter to automatically apply those efficiency factors.
- **Fertigation Planning**: `generate_fertigation_plan` produces a day-by-day
  fertilizer schedule using those irrigation targets.
- **Comprehensive Fertigation**: `recommend_precise_fertigation` adjusts for
  existing water nutrient levels, can include micronutrients, and returns cost
  estimates along with any water quality warnings.
- **Transpiration Averages**: `compute_transpiration_series` calculates mean ET
  and water loss across multiple environment readings. A new `weights`
  parameter lets you apply weighted averages when readings span different
  durations.
- **Fertigation Cost Reporting**: `run_daily_cycle` writes the estimated cost of
  its generated `fertigation_schedule` under the `fertigation_cost` field.
- **Nutrient Profile Analysis**: `analyze_nutrient_profile` combines macro and
  micro guidelines with interaction checks to summarize deficiencies and
  surpluses at once.
- **Nutrient Interaction Details**: `analyze_interactions` returns ratios,
  messages and corrective actions for any detected nutrient imbalances.
- **Deficit-Based Fertilizer Suggestions**: `RecommendationEngine` now recommends products using nutrient guidelines when sensor readings fall short.
- **Daily Nutrient Report**: `run_daily_cycle` now embeds this analysis under
  `nutrient_analysis` to highlight imbalances in recent applications.
- **Pruning Recommendations**: Call `get_pruning_instructions` for stage-specific
  pruning tips loaded from `pruning_guidelines.json`.
- **Pruning Schedule Planning**: Use `get_pruning_interval` and `next_pruning_date`
  to determine when each plant should be pruned based on `pruning_intervals.json`.
- **Fertigation Intervals**: `get_fertigation_interval` and `next_fertigation_date`
  provide recommended application spacing using `fertigation_intervals.json`.
- **Beneficial Insect Suggestions**: Daily reports list natural predators for
  observed pests using `beneficial_insects.json`.
- **Bioinoculant Recommendations**: `get_recommended_inoculants` returns
  microbial products that enhance nutrient uptake based on
  `bioinoculant_guidelines.json`.
- **Biological Control Helper**: `recommend_biological_controls` suggests
  beneficial insects to deploy when pest thresholds are exceeded.
- **IPM Guidance**: `recommend_ipm_actions` returns cultural practices and
  crop-specific actions from `ipm_guidelines.json`.
- **Pest Monitoring Report**: `generate_pest_report` combines severity,
  treatment, biological control, severity actions and prevention advice for observed pests using `pest_severity_actions.json`.
- **Pest Scouting Intervals**: `get_pest_monitoring_interval` returns recommended days between checks using `pest_monitoring_intervals.json`.
- **Next Scouting Date**: `next_monitor_date` adds ``timedelta`` days to the last
  scouting date based on these intervals.
- **Disease Monitoring Report**: `generate_disease_report` now provides
  severity and treatment guidance based on new `disease_thresholds.json`.
- **Harvest Date Prediction**: If plant profiles include a `start_date`, daily
  reports provide an estimated harvest date based on `growth_stages.json`.
- **Stage Schedule Planner**: `build_stage_schedule` returns the expected start
  and end date of each growth stage when given a planting date.
- **Stage Progress Remaining**: `days_until_next_stage` reports how many days
  remain in the current stage based on `growth_stages.json`.
- **Yield Estimation**: `estimate_remaining_yield` compares logged harvests to
  expected totals from `yield_estimates.json`.
  Daily reports now expose this value under `remaining_yield_g` for quick
  tracking.
- **Environment Quality Rating**: `classify_environment_quality` converts the
  numeric score from `score_environment` into `good`, `fair` or `poor` for
  quick evaluation.
- **Environment Score Breakdown**: `score_environment_components` returns
  per-parameter scores so problem areas are easy to identify.
- **Overall Environment Score**: `score_overall_environment` combines
  environment quality with water test results for a single rating.
- **Photoperiod Suggestions**: `recommend_photoperiod` returns the daily light
  hours required to hit midpoint DLI targets at the current PPFD.
- **Light Intensity Suggestions**: `recommend_light_intensity` calculates the
  PPFD needed to achieve midpoint DLI targets for a given photoperiod.
- **Photoperiod Guidelines**: `get_target_photoperiod` looks up recommended day lengths from `photoperiod_guidelines.json`.
- **CO₂ Guidelines**: `get_target_co2` returns recommended enrichment ranges for each stage.
- **CO₂ Injection Calculator**: `calculate_co2_injection` estimates the grams of CO₂ needed to hit the target range based on greenhouse volume.
- **Environment Summary**: `summarize_environment` returns the quality rating
  alongside recommended adjustments and calculated metrics in one step.
- **Metrics From Data Series**: `calculate_environment_metrics_series` averages
  multiple readings to compute VPD, dew point and transpiration over time.
- **Advanced Setpoints**: `suggest_environment_setpoints_advanced` derives
  humidity targets from VPD guidelines when direct values are unavailable.
- **Water Quality Scoring**: `score_water_quality` evaluates irrigation water and
  returns a 0‑100 rating based on toxicity thresholds.
- **Water Quality Summary**: `summarize_water_profile` combines baseline
  readings with warnings, rating and score in one step.
- **Guideline Summary**: `get_guideline_summary` consolidates environment,
  nutrient, irrigation and pest guidance for quick reference.
- **Nutrient Score Trend**: `score_nutrient_series` averages multiple nutrient
  samples to quickly gauge overall balance over time.
- **Environment Targets in Reports**: Daily report files now include the
  recommended temperature, humidity, light and CO₂ ranges for the plant's
  current stage.


### Automation Blueprint Guide
To start quickly, copy `plant_monitoring.yaml` from `blueprints/automation/` into `<config>/blueprints/automation/>` and create a new automation in Home Assistant.
Select the corresponding sensors and plant profile when prompted. Ensure each sensor uses `state_class: measurement` so statistics record correctly.


---

## Roadmap
- [x] Dynamic automation generation per plant
- [x] Tag based grouping and InfluxDB integration
- [ ] Enhanced AI models for nutrient predictions
- [ ] Optional dashboards and computer vision tools
- [ ] Fully autonomous headless mode

---

## Contributing
Development is private for now. Feedback is welcome, but pull requests will open once the repository becomes public. Please open discussions or issues for questions or suggestions.

## Command Line Utilities
This repository ships with a few helper scripts in the `scripts/` directory. The
`generate_plant_sensors.py` utility converts daily JSON reports into Home
Assistant template sensor YAML. Run it with:

```bash
python scripts/generate_plant_sensors.py <plant_id>
```
The generated YAML is written to `templates/generated/` for easy import.

`export_all_growth_yield.py` aggregates growth and yield data from the
`analytics/` directory into a single JSON file:

```bash
python -m custom_components.horticulture_assistant.analytics.export_all_growth_yield
```

The `load_all_profiles` helper can validate and aggregate every profile in the
`plants/` directory. It returns a mapping of plant IDs to structured results:

```python
from custom_components.horticulture_assistant.utils.load_all_profiles import load_all_profiles

profiles = load_all_profiles(validate=True)
for pid, result in profiles.items():
    print(pid, result.loaded, result.issues)
```

To quickly discover which profiles exist without loading them, use the
`list_available_profiles` helper:

```python
from custom_components.horticulture_assistant.utils.plant_profile_loader import (
    list_available_profiles,
)

ids = list_available_profiles()
print(ids)
```

## Troubleshooting
- **Sensors show `unavailable`**: verify the entity IDs and that the devices are reporting to Home Assistant.
- **Config flow fails**: check the logs for JSON errors in your plant profiles or missing permissions.
- **Incorrect nutrient data**: the built-in datasets are for reference only.
  Verify recommendations with a trusted horticulture resource before applying.
- **Blueprint missing**: copy `plant_monitoring.yaml` to `<config>/blueprints/automation/` and restart Home Assistant.

## Running Tests
Run the unit tests with:

```bash
pytest -q
```

---

## References
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Publishing Guide](https://hacs.xyz/docs/publish/start)
- [Home Assistant Blueprints](https://www.home-assistant.io/docs/automation/using-blueprints/)
- [YAML Lint Documentation](https://yamllint.readthedocs.io/)

## License
The source code is shared for reference while development continues.
All datasets are provided **as is** without warranty. Redistribution is not
currently permitted.
