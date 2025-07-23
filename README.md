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
- Heat stress warnings using heat index thresholds
- Humidity stress warnings when humidity is outside safe ranges
- Light stress detection using DLI ranges
- Stage-adjusted nutrient targets
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
- `water_quality_thresholds.json` – acceptable ion limits for irrigation water
- `water_quality_actions.json` – recommended treatments when limits are exceeded
- `fertilizer_purity.json` – default purity factors for common fertilizers
- `fertilizer_solubility.json` – maximum solubility (g/L) for fertilizers
- `heat_stress_thresholds.json` – heat index limits used for stress warnings
- `cold_stress_thresholds.json` – minimum temperature limits for cold stress
- `wind_stress_thresholds.json` – maximum safe wind speed before damage
- `nutrient_deficiency_treatments.json` – remedies for common nutrient shortages
- `nutrient_surplus_actions.json` – steps to mitigate excess nutrient levels
- `nutrient_interactions.json` – warning ratios for antagonistic nutrients
- `nutrient_toxicity_thresholds.json` – upper limits to flag potential toxicity
- `photoperiod_guidelines.json` – recommended day length by crop stage
- `nutrient_toxicity_symptoms.json` – visual cues indicating nutrient excess
- `nutrient_toxicity_treatments.json` – suggested mitigation steps for toxicity
- `growth_stages.json` – lifecycle stage durations and notes by crop
- `pruning_guidelines.json` – stage-specific pruning recommendations
- `soil_texture_parameters.json` – default field capacity and MAD values by soil texture
- `root_depth_guidelines.json` – typical maximum root depth (cm) for common crops
- `irrigation_guidelines.json` – default daily irrigation volume per plant stage
- `irrigation_efficiency.json` – efficiency factors for common irrigation methods
- `foliar_feed_guidelines.json` – recommended nutrient ppm for foliar sprays
- `yield/` – per‑plant yield logs created during operation
- `plant_density_guidelines.json` – recommended plant spacing (cm) for density calculations
- `wsda_fertilizer_database.json` – full fertilizer analysis database used by
  `plant_engine.wsda_lookup` for product N‑P‑K values

All dataset lookups are case-insensitive and ignore spaces thanks to the
`normalize_key` helper, so references such as `"Citrus"` and `"citrus"` map to
the same entries.

You can override the default `data/` directory by setting the environment
variable `HORTICULTURE_DATA_DIR` when running scripts or tests. An additional
`HORTICULTURE_OVERLAY_DIR` may contain files that override or extend those
datasets without copying the entire directory.

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
- **Dynamic Tags**: Tag plants (e.g. `"blueberry"`, `"fruiting"`) to generate grouped dashboards.
- **Nutrient Mix Helper**: The `recommend_nutrient_mix` function computes exact
  fertilizer grams needed to hit N/P/K targets and can optionally include
  micronutrients using the new `micronutrient_guidelines.json` dataset.
- **Mix Cost Estimation**: `recommend_nutrient_mix_with_cost` returns the same
  schedule along with an estimated dollar cost based on fertilizer prices.
- **Mix Nutrient Totals**: `calculate_mix_nutrients` reports the elemental
  nutrient amounts contributed by each fertilizer mix in milligrams.
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
  milliliters per plant based on `irrigation_guidelines.json`.
- **Irrigation Efficiency**: `adjust_irrigation_for_efficiency` scales volumes
  based on delivery method using `irrigation_efficiency.json`.
- **Fertigation Planning**: `generate_fertigation_plan` produces a day-by-day
  fertilizer schedule using those irrigation targets.
- **Comprehensive Fertigation**: `recommend_precise_fertigation` adjusts for
  existing water nutrient levels, can include micronutrients, and returns cost
  estimates along with any water quality warnings.
- **Nutrient Profile Analysis**: `analyze_nutrient_profile` combines macro and
  micro guidelines with interaction checks to summarize deficiencies and
  surpluses at once.
- **Daily Nutrient Report**: `run_daily_cycle` now embeds this analysis under
  `nutrient_analysis` to highlight imbalances in recent applications.
- **Pruning Recommendations**: Call `get_pruning_instructions` for stage-specific
  pruning tips loaded from `pruning_guidelines.json`.
- **Beneficial Insect Suggestions**: Daily reports list natural predators for
  observed pests using `beneficial_insects.json`.
- **Biological Control Helper**: `recommend_biological_controls` suggests
  beneficial insects to deploy when pest thresholds are exceeded.
- **Pest Monitoring Report**: `generate_pest_report` combines severity,
  treatment, biological control, severity actions and prevention advice for observed pests using `pest_severity_actions.json`.
- **Disease Monitoring Report**: `generate_disease_report` now provides
  severity and treatment guidance based on new `disease_thresholds.json`.
- **Harvest Date Prediction**: If plant profiles include a `start_date`, daily
  reports provide an estimated harvest date based on `growth_stages.json`.
- **Stage Schedule Planner**: `build_stage_schedule` returns the expected start
  and end date of each growth stage when given a planting date.
- **Yield Estimation**: `estimate_remaining_yield` compares logged harvests to
  expected totals from `yield_estimates.json`.
  Daily reports now expose this value under `remaining_yield_g` for quick
  tracking.
- **Environment Quality Rating**: `classify_environment_quality` converts the
  numeric score from `score_environment` into `good`, `fair` or `poor` for
  quick evaluation.
- **Environment Score Breakdown**: `score_environment_components` returns
  per-parameter scores so problem areas are easy to identify.
- **Photoperiod Suggestions**: `recommend_photoperiod` returns the daily light
  hours required to hit midpoint DLI targets at the current PPFD.
- **Light Intensity Suggestions**: `recommend_light_intensity` calculates the
  PPFD needed to achieve midpoint DLI targets for a given photoperiod.
- **Photoperiod Guidelines**: `get_target_photoperiod` looks up recommended day lengths from `photoperiod_guidelines.json`.
- **Environment Summary**: `summarize_environment` returns the quality rating
  alongside recommended adjustments and calculated metrics in one step.
- **Water Quality Scoring**: `score_water_quality` evaluates irrigation water and
  returns a 0‑100 rating based on toxicity thresholds.
- **Guideline Summary**: `get_guideline_summary` consolidates environment,
  nutrient and pest guidance for quick reference.
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
