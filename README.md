# Horticulture Assistant

Horticulture Assistant integrates per-plant automation and crop monitoring into Home Assistant. It exposes sensors, switches and scripts so you can manage irrigation, nutrient plans and plant health from one dashboard.

---

## Table of Contents
- [Overview](#overview)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [HACS](#hacs)
  - [Manual](#manual)
- [Features](#features)
- [Working with Plant Profiles](#working-with-plant-profiles)
  - [Profile Format](#profile-format)
  - [Plant Registry](#plant-registry)
- [Reference Data](#reference-data)
- [Command Line Utilities](#command-line-utilities)
- [Advanced Usage](#advanced-usage)
- [Repository Structure](#repository-structure)
- [Troubleshooting](#troubleshooting)
- [Running Tests](#running-tests)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [References](#references)
- [License](#license)

---

## Overview
This integration is under active development. It gathers environmental data, computes nutrient recommendations and can optionally leverage AI models to refine your crop schedule. The goal is full hands‑off operation with the ability to review and approve changes in Home Assistant.

### Safety & Disclaimer
The bundled datasets are not exhaustive and may contain inaccuracies. Always cross‑check nutrient and treatment advice with a local agronomist before applying it to your plants.

---

## Quick Start
1. Go to **Settings → Devices & Services** in Home Assistant.
2. Choose **Add Integration** and search for **Horticulture Assistant**.
3. Follow the prompts to link sensors and select or create plant profiles.
4. Copy `blueprints/automation/plant_monitoring.yaml` into `<config>/blueprints/automation/>` and create an automation from it.
5. Enable `input_boolean.auto_approve_all` if you want AI recommendations applied automatically.
6. Ensure all numeric sensors use `state_class: measurement` so statistics are recorded.

Plant profiles are stored in the `plants/` directory and can be created through the config flow or edited manually.

---

## Installation
### HACS
1. Open HACS and navigate to **Integrations → Custom Repositories**.
2. Add this repository URL and install **Horticulture Assistant** from the list.
3. Restart Home Assistant when prompted.

### Manual
1. Clone this repository.
2. Copy `custom_components/horticulture_assistant/` into your Home Assistant `config/custom_components/` directory.
3. Restart Home Assistant.

---

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
- Precise pH adjustment volume calculations
- Heat, humidity and light stress warnings
- Stage-adjusted nutrient targets and leaf tissue analysis
- Nutrient deficiency severity and treatment recommendations
- Daily report files summarizing environment and nutrient targets

---

## Working with Plant Profiles
### Profile Format
Plant profiles are JSON files placed in the `plants/` directory. A minimal example:
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

### Plant Registry
Multiple profiles can be indexed in `plant_registry.json` so automations can discover them easily. Example:
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

## Reference Data
The `data/` directory contains many reference datasets. Use `dataset_catalog.json` to see short descriptions for each file.

Important categories include:
- **Environment guidelines** – optimal temperature, humidity, light and CO₂ ranges
- **Nutrient guidelines** – macronutrient and micronutrient targets by stage
- **Pest and disease references** – thresholds, prevention tips and treatment options
- **Irrigation and water quality** – daily volume guidelines, quality thresholds and cost estimates
- **Fertilizer and product data** – WSDA fertilizer database and recipe suggestions

Datasets can be overridden by setting environment variables:
- `HORTICULTURE_DATA_DIR` to change the base data directory
- `HORTICULTURE_OVERLAY_DIR` to merge in custom files
- `HORTICULTURE_EXTRA_DATA_DIRS` to load additional datasets
Call `plant_engine.utils.clear_dataset_cache()` after adjusting these variables so changes are reflected immediately.

---

## Command Line Utilities
Helper scripts live in the `scripts/` directory.

- `generate_plant_sensors.py` converts daily reports into Home Assistant template sensor YAML.
- `wsda_search.py` queries the bundled WSDA fertilizer database.
- `export_all_growth_yield.py` aggregates growth and yield data from the `analytics/` directory.
- `load_all_profiles` validates and aggregates every profile in the `plants/` directory.
- `list_available_profiles` quickly lists profile IDs without loading them.

Example usage:
```bash
python scripts/generate_plant_sensors.py <plant_id>
python scripts/wsda_search.py "EARTH-CARE" --limit 5
python -m custom_components.horticulture_assistant.analytics.export_all_growth_yield
```

---

## Advanced Usage
- Use the automation blueprints under `blueprints/automation/` for quick setup.
- Toggle `input_boolean.auto_approve_all` to apply AI recommendations automatically.
- Edit `plant_engine/constants.py` to tweak default environment readings or nutrient multipliers when profiles omit them.
- Call `plant_engine.datasets.refresh_datasets()` if dataset files change.
- Tag plants (e.g. `"blueberry"`, `"fruiting"`) to generate grouped dashboards and reports.
- `recommend_nutrient_mix` computes fertilizer grams needed to hit N/P/K targets and can include micronutrients. `recommend_nutrient_mix_with_cost` returns the same schedule with estimated cost.
- `get_pruning_instructions` provides stage-specific pruning tips from `pruning_guidelines.json`.
- `generate_cycle_irrigation_plan` returns stage irrigation volumes using guideline intervals and durations.

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

---

## Troubleshooting
- **Sensors show `unavailable`**: verify the entity IDs and that the devices are reporting to Home Assistant.
- **Config flow fails**: check the logs for JSON errors in your plant profiles or missing permissions.
- **Incorrect nutrient data**: the built-in datasets are for reference only. Verify recommendations with a trusted horticulture resource before applying.
- **Blueprint missing**: copy `plant_monitoring.yaml` to `<config>/blueprints/automation/` and restart Home Assistant.

---

## Running Tests
Install the dependencies and run `pytest`:
```bash
pip install -r requirements.txt
pytest -q
```

---

## Roadmap
- [x] Dynamic automation generation per plant
- [x] Tag based grouping and InfluxDB integration
- [ ] Enhanced AI models for nutrient predictions
- [ ] Optional dashboards and computer vision tools
- [ ] Fully autonomous headless mode

---

## Contributing
Development is currently private. Feedback is welcome, but pull requests will open once the repository becomes public. Please open discussions or issues for questions or suggestions.

## References
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Publishing Guide](https://hacs.xyz/docs/publish/start)
- [Home Assistant Blueprints](https://www.home-assistant.io/docs/automation/using-blueprints/)
- [YAML Lint Documentation](https://yamllint.readthedocs.io/)

## License
The source code is shared for reference while development continues. All datasets are provided **as is** without warranty. Redistribution is not currently permitted.
