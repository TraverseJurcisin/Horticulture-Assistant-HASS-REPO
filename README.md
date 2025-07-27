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
  - [Managing Existing Profiles](#managing-existing-profiles)
- [Reference Data](#reference-data)
- [Command Line Utilities](#command-line-utilities)
- [Advanced Usage](#advanced-usage)
- [Garden Summary Lovelace Card](#garden-summary-lovelace-card)
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
3. Enter a plant name and (optionally) a zone ID to start the profile.
4. If a matching template isn't found, a placeholder entry is created and you can complete the details later in **Options**.
5. Open the entry's **Options** anytime to update the zone, enable auto‑approve or link sensors.
6. Copy `blueprints/automation/plant_monitoring.yaml` into `<config>/blueprints/automation/>` and create an automation from it.
7. Enable `input_boolean.auto_approve_all` if you want AI recommendations applied automatically.
8. Ensure all numeric sensors use `state_class: measurement` so statistics are recorded.

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
- Configurable irrigation zones with shared solenoids

### Data & Analytics
- Disease and pest treatment recommendations
- Environment optimization suggestions with pH guidance
- Precise pH adjustment volume calculations
- Heat, humidity and light stress warnings
- Stage-adjusted nutrient targets and leaf tissue analysis
- Nutrient deficiency severity and treatment recommendations
- Daily report files summarizing environment and nutrient targets
- Infiltration-aware irrigation burst scheduling
- Risk-adjusted pest monitoring summaries and scheduling
- Automatic pesticide rotation planning

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

Sensor entity mappings can be defined under `sensor_entities`. Use plural keys
like `"moisture_sensors"` or `"temperature_sensors"` with a list of entity IDs:

```json
{
  "general": {
    "sensor_entities": {
      "moisture_sensors": ["sensor.bed_moist_1", "sensor.bed_moist_2"],
      "temperature_sensors": ["sensor.greenhouse_temp"]
    }
  }
}
```

If multiple entity IDs are provided, their values are averaged. When more than
two sensors are listed, the median of the available readings is used instead to
reduce the effect of outliers.

### Zones and Irrigation Scheduling
Profiles can declare a `zone_id` to group plants under a common irrigation
zone. Zones and their associated solenoids are defined in `zones.json`. Each
zone entry lists the solenoid switches that must be opened for watering and may
be referenced by multiple plants.

You can set the zone ID during the config flow or later via **Options**. Use the
helper functions in `zone_registry` to add zones or attach plants to a zone
programmatically. For example:

```python
from custom_components.horticulture_assistant.utils import zone_registry

zone_registry.add_zone("3", ["switch.valve_3a", "switch.valve_3b"])
zone_registry.attach_plants("3", ["plant_a", "plant_b"])
zone_registry.attach_solenoids("3", ["switch.extra_valve"])
```

Irrigation settings are placed under `irrigation_schedule` with a `method`
value of `time_pattern`, `volume`, `moisture` or `pulsed`. The required keys
vary by method but a simple timed schedule looks like this:

```json
{
  "general": {"zone_id": "3"},
  "irrigation_schedule": {
    "method": "time_pattern",
    "time": "06:00",
    "duration_min": 10
  }
}
```

You can update the sensor mapping later using the ``horticulture_assistant.update_sensors`` service:

```yaml
service: horticulture_assistant.update_sensors
data:
  plant_id: citrus_backyard_spring2025
  sensors:
    moisture_sensors:
      - sensor.new_moisture
    temperature_sensors:
      - sensor.new_temp
      - sensor.backup_temp
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

## Managing Existing Profiles
Use `profile_manager.py` to update sensor mappings, view log history and tweak
preferences without editing JSON files. The script lives in the `scripts/`
directory and accepts several subcommands:

```bash
# add or remove sensor entity IDs
python scripts/profile_manager.py attach-sensor <plant_id> <sensor_type> sensor.a sensor.b
python scripts/profile_manager.py detach-sensor <plant_id> <sensor_type> sensor.a
python scripts/profile_manager.py list-sensors <plant_id>

# read the last entries from a log
python scripts/profile_manager.py show-history <plant_id> events --lines 10

# change preferences like automation flags
python scripts/profile_manager.py set-pref <plant_id> auto_approve_all true

# load a new local profile from a global template
python scripts/profile_manager.py list-globals
python scripts/profile_manager.py load-default tomato my_tomato

# override default paths
python scripts/profile_manager.py attach-sensor myplant moisture sensor.new --plants-dir /path/to/profiles \
  --global-dir /path/to/global_templates
```


---

## Reference Data
The `data/` directory contains many reference datasets. Use `dataset_catalog.json` to see short descriptions for each file.

Important categories include:
- **Environment guidelines** – optimal temperature, humidity, light and CO₂ ranges
- **Environment actions** – recommended steps when temperature or humidity are out of range
- **Nutrient guidelines** – macronutrient and micronutrient targets by stage
- **Pest and disease references** – thresholds, prevention tips and treatment options
- **Pest scouting methods** – recommended techniques for monitoring common pests
- **Irrigation and water quality** – daily volume guidelines, quality thresholds and cost estimates
- **Canopy area** – approximate canopy area by growth stage for transpiration calculations
- **Fertilizer and product data** – WSDA fertilizer database and recipe suggestions
- **Soil pH guidelines** – optimal soil pH ranges for supported crops

The WSDA fertilizer dataset resides under `feature/wsda_refactored_sharded/` which contains an
`index_sharded/` directory of `.jsonl` shards and a `detail/` directory of per-product records.
You can override the location by setting ``WSDA_DATA_DIR`` or the more specific ``WSDA_INDEX_DIR`` and
``WSDA_DETAIL_DIR`` environment variables. Each product's detail file is stored in a subdirectory
named after the first two characters of its ``product_id``.
These records follow the **2025-07-v1** schema which adds fields like
`non_plant_food_ingredients` and consolidates company information under `metadata`.
Recent updates expanded the dataset with dozens of General Hydroponics fertilizer and pesticide records.

Example usage:

```python
from plant_engine.wsda_loader import stream_index, load_detail

for prod in stream_index():
    if prod["brand"] == "ACME SOILS":
        detail = load_detail(prod["product_id"])
        print(detail["metadata"]["label_name"])
```

Datasets can be overridden by setting environment variables:
- `HORTICULTURE_DATA_DIR` to change the base data directory
- `HORTICULTURE_OVERLAY_DIR` to merge in custom files
- `HORTICULTURE_EXTRA_DATA_DIRS` to load additional datasets
Call `plant_engine.utils.clear_dataset_cache()` after adjusting these variables so changes are reflected immediately.

---

## Command Line Utilities
Helper scripts live in the `scripts/` directory.

- `generate_plant_sensors.py` converts daily reports into Home Assistant template sensor YAML.
- `generate_guideline_summary.py` outputs consolidated environment, nutrient and pest guidance for a crop stage.
- `wsda_search.py` queries the bundled WSDA fertilizer database.
- `log_runoff_ec.py` records manual runoff EC measurements for calibration.
- `train_ec_model.py` generates EC estimator coefficients from a CSV dataset. Use
  `--plant-id` to save a model under that plant's profile.
- `export_all_growth_yield.py` aggregates growth and yield data from the `analytics/` directory.
- `load_all_profiles` validates and aggregates every profile in the `plants/` directory.
- `list_available_profiles` quickly lists profile IDs without loading them.
- `fertigation_plan.py` creates a JSON fertigation schedule for any crop stage.
- `backup_profiles.py` manages ZIP backups of plant profiles and the registry. Use `--list` to view archives, `--restore` to unpack one, `--verify` to check an archive, `--retain` to limit how many are kept, and `--root` to operate on an alternate data directory.
- `profile_manager.py` manages sensors, preferences, and templates.  `attach-sensor` appends new sensors, while `detach-sensor` removes them.  Other subcommands include `list-sensors`, `set-pref`, `load-default`, `show-history`, and `list-globals`.  `--plants-dir` and `--global-dir` operate on alternate directories.

Example usage:
```bash
python scripts/generate_plant_sensors.py <plant_id>
python scripts/wsda_search.py "EARTH-CARE" --limit 5
python scripts/log_runoff_ec.py <plant_id> <ec_value>
python scripts/train_ec_model.py samples.csv --plant-id myplant
python scripts/profile_manager.py load-default tomato my_plant
python scripts/profile_manager.py list-sensors my_plant
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

### Garden Summary Lovelace Card
Add `garden-summary-card.js` as a Lovelace resource (HACS places it under
`/hacsfiles/horticulture_assistant/dashboard/`) to quickly see the status of all
plants and highlight any requiring attention.

```yaml
resources:
  - url: /hacsfiles/horticulture_assistant/dashboard/garden-summary-card.js
    type: module
```

Example card configuration:

```yaml
type: custom:garden-summary-card
title: Garden Overview
# optional card-wide thresholds
depletion_threshold: 80
bad_quality_state: poor
plants:
  - id: citrus_backyard_spring2025
    name: Backyard Citrus
    moisture_entity: sensor.citrus_moisture
    quality_entity: sensor.citrus_env_quality
    depletion_entity: sensor.citrus_depletion
    # plant-specific overrides
    depletion_threshold: 75
    bad_quality_state: critical
  - id: basil_kitchen_2025
    name: Kitchen Basil
    # uses default sensor names
```

The Priority column displays a check or alert icon. Plants with a root zone
depletion above 80% or an environment quality rated `poor` show the alert
icon. The card reads the following
sensors for each `plant_id`:

- `sensor.<plant_id>_smoothed_moisture`
- `sensor.<plant_id>_env_quality`
- `sensor.<plant_id>_depletion`

Sensors can be overridden per plant using `moisture_entity`, `quality_entity`
and `depletion_entity` keys. When omitted, the default entity IDs above are
assumed. Each plant entry may also override `depletion_threshold` and
`bad_quality_state` to fine tune the warning criteria.

Two optional card-level settings control the priority criteria:

- `depletion_threshold` &ndash; numeric percentage for the depletion warning (default `80`)
- `bad_quality_state` &ndash; environment quality state that triggers a warning (default `poor`)

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
