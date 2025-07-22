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
- Stage-adjusted nutrient targets
- Example crop profiles for strawberries, basil, spinach and more

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
- `pest_thresholds.json` – action thresholds for common pests
- `beneficial_insects.json` – natural predator recommendations for pests
- `water_quality_thresholds.json` – acceptable ion limits for irrigation water
- `fertilizer_purity.json` – default purity factors for common fertilizers
- `nutrient_deficiency_treatments.json` – remedies for common nutrient shortages
- `growth_stages.json` – lifecycle stage durations and notes by crop
- `yield/` – per‑plant yield logs created during operation
- `wsda_fertilizer_database.json` – full fertilizer analysis database used by
  `plant_engine.wsda_lookup` for product N‑P‑K values

You can override the default `data/` directory by setting the environment
variable `HORTICULTURE_DATA_DIR` when running scripts or tests.

The datasets are snapshots compiled from public resources. They may be outdated
or incomplete and should only be used as a starting point for your own research.


---

## Advanced Topics
- **YAML Automations**: Use the blueprints in `blueprints/automation/` for easy setup.
- **Custom Plant Profiles**: Drop JSON profiles in `plants/` for per‑plant settings.
- **Auto Approval**: Toggle `input_boolean.auto_approve_all` to apply AI recommendations automatically.
- **Data Logging**: Set `state_class: measurement` on sensors for proper history recording.
- **Dynamic Tags**: Tag plants (e.g. `"blueberry"`, `"fruiting"`) to generate grouped dashboards.
- **Nutrient Mix Helper**: The `recommend_nutrient_mix` function computes exact
  fertilizer grams needed to hit N/P/K targets and can optionally include
  micronutrients using the new `micronutrient_guidelines.json` dataset.
- **Daily Uptake Estimation**: Use `estimate_daily_nutrient_uptake` to convert
  ppm guidelines and irrigation volume into milligrams of nutrients consumed
  each day.
- **Total Uptake Estimation**: `estimate_total_uptake` multiplies daily uptake
  by growth stage durations from `growth_stages.json` to calculate nutrients
  required for an entire crop cycle.


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
This repository ships with a few helper scripts under the root directory. The
`Template Sensor Generator (generate_plant_sensors.py)` script converts daily
JSON reports into Home Assistant template sensor YAML. Run it with:

```bash
python "Template Sensor Generator (generate_plant_sensors.py)" <plant_id>
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
