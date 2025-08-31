# Horticulture Assistant (Home Assistant Custom Integration)

Manage plants like data-driven digital twins in Home Assistant.
Profiles combine sensor readings, derived metrics, scientific horticulture parameters, and optional AI recommendations to give growers—from hobbyists to greenhouse managers—a complete plant care assistant.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
- [Services](#services)
- [Example Profile: Avocado (*Persea americana*)](#example-profile-avocado-persea-americana)
- [Appendix: Horticulture Profile Template](#appendix-horticulture-profile-template)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Features

### Plant Profiles
Create modular, per-plant profiles (e.g., Avocado, Citrus, Tomato) that persist locally. Profiles integrate environmental, physiological, and horticultural data.

### Sensor Linking
Map real sensors (temperature, humidity, illuminance, soil moisture, CO₂, etc.) to each profile.

### Derived Metrics
- Daily Light Integral (DLI)
- Vapor Pressure Deficit (VPD)
- Dew Point
- Mold Risk Index (based on T/RH dynamics)
- Growth stage-aware flags (light OK, moisture OK, environment OK)

### Config/Options Flow
Add or edit profiles directly in Settings → Devices & Services.

### Local-first Storage
Profiles are JSON on disk. You can export/import them, diff them, and version them.

### Optional AI
If configured, generate AI-driven recommendations and approve them into profiles.

### Irrigation Hooks
Service endpoints to push irrigation plans to schedulers like Irrigation Unlimited or controllers like OpenSprinkler.

### Diagnostics
One-click redacted export of profile and coordinator state for support/debugging.

## Installation

### HACS (Custom Repository)
1. In Home Assistant: HACS → Integrations → ⋮ → Custom repositories.
2. Add this repository URL and choose **Integration** as the category.
3. Search for Horticulture Assistant in HACS and install.
4. Restart Home Assistant.

### Manual
1. Download the latest release ZIP.
2. Copy `custom_components/horticulture_assistant/` into your Home Assistant `config` directory (e.g. `config/custom_components/horticulture_assistant`).
3. Restart Home Assistant.

## Configuration

1. Add Integration: Settings → Devices & Services → Add Integration → Horticulture Assistant
2. Create a profile: Give it a name, optionally select a species/template.
3. Link sensors: Pick your existing HA sensors.
4. Set thresholds: Manually enter or clone from another profile.
5. Entities appear under a device for that plant profile.

## Entities

Per profile, you can expect entities like:

- `sensor.<plant>_dli` (Daily Light Integral, mol·m⁻²·d⁻¹)
- `sensor.<plant>_vpd` (kPa)
- `sensor.<plant>_dew_point` (°C/°F)
- `binary_sensor.<plant>_light_ok`
- `binary_sensor.<plant>_moisture_ok`
- `binary_sensor.<plant>_environment_ok`

Attributes include linked sensor IDs, thresholds, warnings, and last recommendation metadata.

## Services

All services are documented in `services.yaml` and visible in HA’s UI.

Examples:

- `horticulture_assistant.create_profile`
- `horticulture_assistant.duplicate_profile`
- `horticulture_assistant.delete_profile`
- `horticulture_assistant.update_sensors`
- `horticulture_assistant.recompute`
- `horticulture_assistant.generate_profile` (clone / AI / species template)
- `horticulture_assistant.apply_irrigation_plan`
- `horticulture_assistant.export_profile`
- `horticulture_assistant.import_profiles`

## Example Profile: Avocado (*Persea americana*)

### Description
Uses: Edible fruit, oil, ornamental shade tree

Duration: Perennial (long-lived tree)

Habit: Evergreen tree, 15–20 m tall

Key features: High oil content fruit, sensitive to cold

### Environmental thresholds (generalized)
- Air temperature: 18–26 °C ideal, <5 °C damage risk
- RH: 50–70%
- DLI: 20–30 mol·m⁻²·d⁻¹
- Soil pH: 5.5–7.0
- Soil moisture: Avoid waterlogging; moderate dry-back tolerated

### Entities in HA
- `sensor.avocado_dli`
- `sensor.avocado_vpd`
- `binary_sensor.avocado_environment_ok`

### Profile JSON (excerpt)
```json
{
  "name": "Avocado",
  "sensors": {
    "temperature": "sensor.greenhouse_temp",
    "humidity": "sensor.greenhouse_rh",
    "illuminance": "sensor.par_meter",
    "moisture": "sensor.soil_probe"
  },
  "thresholds": {
    "temp_min": 18,
    "temp_max": 26,
    "rh_min": 50,
    "rh_max": 70,
    "dli_target": 25
  }
  }
```

## Appendix: Horticulture Profile Template

This integration uses a structured Horticulture Profile Template to guide how plant data is captured and organized. The template covers:

- Introduction & Cultural History: origin, uses, domestication, cultural significance
- Morphology: leaf, root, growth form, mechanical adaptations
- Ecophysiology: defenses, microbiota interactions, storm/wind resistance
- Reproductive Biology: pollination ecology, triggers for flowering & fruit set
- Fruit & Harvest: development, timing, yield density, storage & markets
- Cultivation Requirements: stage-based needs for light (PPFD/Lux/DLI), temperature, humidity/VPD, airflow, CO₂, fertigation, soil/media
- Nutritional Requirements: macronutrients, micronutrients, deficiency & toxicity ranges, heavy metal caution
- Pests & Pathogens: stage-specific pest pressure and ID notes
- Training & Pruning: structural support and methods
- Profile Versioning: version tags to track updates

By using this template, profiles remain modular, scientifically rigorous, and adaptable across species.

## Roadmap

- Add species search and template presets (local and optional AI)
- Expand derived sensors (chlorophyll index, stress indices)
- Better irrigation planners (ET-based, stage-aware)
- Dashboard examples using the Lovelace Flower Card style
- Profile versioning UI

## Contributing

Fork, branch, and open PRs.

Run `pre-commit run --all-files` and `pytest -q` before pushing.

Add/update JSON schemas for new data types.

## License

MIT (see `LICENSE`).
