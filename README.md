# Horticulture-Assistant

The **Horticulture-Assistant** integration provides per-plant automation and monitoring for Home Assistant. It exposes sensors, switches and scripts that help track growth, schedule irrigation and adjust nutrient programs.

This repository is structured as a custom HACS integration but is currently private while development continues.

---

### Plant Monitoring
- Sensors for moisture, EC and nutrient levels
- Environmental data including light intensity and CO₂
- Binary sensors for irrigation readiness and fault detection

### Automation & AI
- Dynamic thresholds based on growth stage and sensor history
- Optional AI models (offline or OpenAI) to refine nutrient plans
- Irrigation and fertigation switches with approval queues

### Data & Analytics
- Built-in nutrient guidelines and fertilizer purity data
- Root zone and water balance utilities for irrigation planning
- New helper to calculate irrigation interval based on ET rates
- Yield tracking with integration to InfluxDB and Grafana
- Tagging system to group plants for aggregated analytics

### Reference Datasets
- Environment guidelines with VPD calculations
- Dew point and climate optimization helpers
- Heat index computation for warm climates
- Disease and pest treatment recommendations
- Example profiles for plants like strawberry, basil and spinach

---

## Installation

### HACS
1. Open HACS in Home Assistant and navigate to **Integrations → Custom Repositories**.
2. Add this repository URL and install **Horticulture-Assistant** from the list.
3. Restart Home Assistant when prompted.

### Manual
1. Clone this repository.
2. Copy `custom_components/horticulture_assistant/` into your Home Assistant `config/custom_components/` folder.
3. Restart Home Assistant.

---

## Getting Started

1. Go to **Settings > Devices & Services** in Home Assistant.
2. Choose **Add Integration** and search for **Horticulture-Assistant**.
3. Follow the prompts to link sensors and configure plant profiles.

Plant profiles and sensors are currently managed manually. A basic config flow exists but remains disabled in the manifest.

---

## Advanced Usage

- **YAML Automations**: Use the blueprints in `blueprints/automation/` for quick setup.
- **Custom Plant Profiles**: Place JSON profiles in `plants/` for per-plant settings.
- **Auto Approval**: Toggle `input_boolean.auto_approve_all` to allow AI recommendations to apply automatically.
- **Data Logging**: Set `state_class: measurement` on sensors to ensure proper recording in InfluxDB.
- **Dynamic Tags**: Tag plants (e.g. `"blueberry"`, `"fruiting"`) for group analytics and dashboards.

---

## Repository Layout

```text
horticulture-assistant/
├── custom_components/horticulture_assistant/
├── blueprints/
├── data/
├── plant_engine/
├── scripts/
├── plants/
├── plant_registry.json
├── tags.json
└── tests/
```

---

## Blueprint & Sensor Notes

To use the automation blueprint:
1. Copy `plant_monitoring.yaml` into `<config>/blueprints/automation/`.
2. In Home Assistant, create a new automation from this blueprint and configure the required entities.

All sensors referenced by automations must define:

```yaml
state_class: measurement
```

This ensures history is recorded correctly for analytics.

---

## Roadmap

- [x] Dynamic automation generation per plant
- [x] Tag-based grouping and InfluxDB integration
- [ ] Enhanced AI models for nutrient predictions
- [ ] Optional dashboards and computer vision tools
- [ ] Fully autonomous mode with headless operation

---

## Contributing

Development happens privately for now. Feedback is welcome but formal issues and pull requests will open once the repository is public.

---

## References

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [HACS Publishing Guide](https://hacs.xyz/docs/publish/start)
- [Home Assistant Blueprints](https://www.home-assistant.io/docs/automation/using-blueprints/)
- [YAML Lint Documentation](https://yamllint.readthedocs.io/)

