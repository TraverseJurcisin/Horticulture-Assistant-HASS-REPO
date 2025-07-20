# Horticulture-Assistant

The **Horticulture-Assistant** integration is a private Home Assistant add-on aimed at managing per‑plant care and horticultural automation.  It provides sensors, switches and helper scripts to monitor plants, track daily growth and optionally adjust nutrient thresholds using simple AI rules.  The repository is structured in a HACS-friendly way but is not yet published through the Community Store.

Currently, this repository is **private and actively under development**. A suitable license will be introduced prior to the public release.

---

## 🌱 Key Features

* Individual plant automation leveraging detailed sensor inputs and dynamic JSON profiles
* Sensors for moisture, EC, ET, nutrient levels and AI recommendations
* Built-in nutrient guidelines for precise fertilizer planning
* Reference datasets for environment, pests and growth stage info
* Fertilizer purity dataset for accurate mixing calculations
* Fertigation utilities support specifying a fertilizer product by name
* Environment guidelines include light intensity and CO₂ ranges
* Automated environment adjustment and pest treatment suggestions
* Disease treatment recommendations for common plant diseases
* On-demand nutrient correction and fertigation calculations
* Tracking nutrient use efficiency from yield and application logs
* Root zone modeling utilities for irrigation planning
* Dynamic water balance using root zone capacity estimates
* Binary sensors for irrigation readiness, sensor health and fault detection
* Switch entities to control irrigation and fertigation
* Approval queue for AI threshold updates with manual review
* Optional AI threshold recalculation using offline or OpenAI logic
* YAML automation blueprint and profile generator utilities
* Plant registry with dynamic tagging for grouped analytics
* Repository structured for use as a custom HACS repository

---

## 🧩 Installation

### Via HACS

1. Open HACS in Home Assistant and go to **Integrations → Custom Repositories**.
2. Add this repository URL as a custom integration.
3. Install **Horticulture-Assistant** from the list and restart Home Assistant when prompted.

### Manual Installation

1. Clone or download this repository.
2. Copy the contents from `custom_components/Horticulture-Assistant/` into `config/custom_components/Horticulture-Assistant/`.
3. Restart Home Assistant.

---

## ⚙️ Configuration – General Users

Post-installation setup:

1. Navigate to **Settings > Devices & Services** in Home Assistant.
2. Click **Add Integration (+)**.
3. Search and select **Horticulture-Assistant**.
4. Follow the guided prompts to configure devices and parameters.

Configuration currently relies on manual setup of plant profiles and sensors. A minimal config flow is included for experimentation but is not fully enabled in the manifest.

---

## 🔧 Advanced Configuration – Power Users

Advanced customization is provided through:

* **YAML-based Automation**: Set up automations using blueprints in `automations/`.
* **Individual Plant Profiles**: Define plant-specific settings in `plants/<plant_id>.json`.
* **Automated Control**: Utilize the toggle `input_boolean.auto_approve_all` for AI-based automation approval.
* **Data Logging**: Ensure sensors have `state_class: measurement` for consistent data capture in InfluxDB.
* **Dynamic Tagging System**: Employ tags such as `"blueberry"`, `"acid-loving"`, or `"fruiting"` for aggregated analytics and insights.

---

## 📁 Repository Structure

```text
horticulture-assistant/
├── custom_components/
│   └── horticulture_assistant/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── const.py
│       ├── sensor.py
│       ├── binary_sensor.py
│       ├── switch.py
│       └── utils/
├── blueprints/
│   └── automation/
│       └── plant_monitoring.yaml
├── data/
│   ├── yield/
│   ├── fertilizer_purity.json
│   └── nutrient_guidelines.json
├── plant_engine/
│   ├── engine.py
│   ├── ai_model.py
│   ├── et_model.py
│   ├── compute_transpiration.py
│   ├── water_deficit_tracker.py
│   ├── growth_model.py
│   ├── nutrient_efficiency.py
│   ├── approval_queue.py
│   ├── disease_manager.py
│   └── nutrient_manager.py
├── scripts/
│   ├── run_all_plants.py
│   ├── daily_threshold_recalc.py
│   ├── compute_transpiration.py
│   ├── growth_model.py
│   ├── nutrient_efficiency.py
│   ├── rootzone_model.py
│   └── ai_model.py
├── plants/
│   └── <plant_id>.json
├── plant_registry.json
├── tags.json
├── README.md
├── .gitignore

```

---

## 🛠️ Blueprint and CI Integration

### Using the Automation Blueprint

1. Copy `plant_monitoring.yaml` into `<config>/blueprints/automation/`.
2. Open Home Assistant, navigate to Automations > Create New > Use Blueprint.
3. Select **Plant Monitoring**.
4. Configure sensors, thresholds, and toggles (including `auto_approve_all`).

### Sensor Configuration Requirements

All sensors referenced must include:

```yaml
state_class: measurement
```

This ensures correct data logging to InfluxDB and accurate historical analytics in Grafana.

### CI Notes

This repository currently does not include automated CI workflows. Validation scripts may be added in a future revision.

---

## 🚀 Planned Roadmap

* [x] Dynamic per-plant automation generation
* [x] AI-based threshold recalculation
* [x] Comprehensive tag-based plant grouping
* [x] Integration with InfluxDB and Grafana
* [ ] Enhanced AI inference capabilities (including offline and OpenAI support)
* [ ] Interactive Lovelace or Grafana dashboards
* [ ] Advanced support for CEC, media type inference, and growth modeling
* [ ] Full yield analytics and crop steering capabilities
* [ ] Computer vision integration for growth tracking
* [ ] Fully autonomous headless automation mode

---

## 🤝 Support & Contributions

This repository is actively developed and maintained. Upon public release, contributions and issue reporting via GitHub will be welcomed. Currently, feedback and testing issues should be directed to the repository author.

---

## 📚 References

* [Home Assistant Developer Documentation](https://developers.home-assistant.io/)
* [HACS Integration Guidelines](https://hacs.xyz/docs/publish/start)
* [Home Assistant Blueprints](https://www.home-assistant.io/docs/automation/using-blueprints/)
* [YAML Lint Documentation](https://yamllint.readthedocs.io/)

---

*This README has been comprehensively revised to reflect the latest architecture pivot, including dynamic tagging, daily AI-driven threshold recalculations, and enhanced automation capabilities.*
