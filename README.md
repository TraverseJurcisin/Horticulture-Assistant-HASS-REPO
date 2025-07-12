# Horticulture-Assistant-Assistant

The **Horticulture-Assistant-Assistant** integration is a comprehensive custom component for Home Assistant, specifically designed to manage plant care and horticultural automation. It enables sophisticated, per-plant monitoring and precise control using advanced configuration logic, AI-driven analytics, and automated processes for irrigation, fertilization, and yield optimization. The integration is **HACS-compatible**, ensuring seamless installation and regular updates via the Home Assistant Community Store.

Currently, this repository is **private and actively under development**. A suitable license will be introduced prior to the public release.

---

## 🌱 Key Features

* Individual plant automation leveraging detailed sensor inputs and comprehensive metadata profiles
* Extensive support for monitoring soil moisture, essential nutrients, and heavy metals
* Automated daily recalculation of optimal growth thresholds utilizing AI insights
* Flexible auto/manual modes for AI-guided lifecycle stage detection
* Structured YAML blueprint-based automation for simplified configuration
* JSON-based plant profile registry supporting dynamic tagging and advanced phylogenetic groupings
* Robust integration with InfluxDB and Grafana for deep analytics and visualization
* Integrated GitHub Actions for continuous integration and validation
* Organized and compliant file structure suitable for HACS

---

## 🧩 Installation

### Via HACS

1. Open HACS in Home Assistant → Integrations → Custom Repositories.
2. Enter your GitHub repository URL, select *Integration*, then click **Add**.
3. Search for **Horticulture-Assistant**, and click **Install**.
4. Restart Home Assistant when prompted.

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

This integration uses Home Assistant’s intuitive UI-based Config Flow. Once configured, users can manage entities, set up custom automations, and monitor plant health.

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
Horticulture-Assistant/
├── README.md                     # Documentation (this file)
├── hacs.json                     # HACS metadata
├── custom_components/
│   └── Horticulture-Assistant/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py       # Optional Config Flow
│       ├── sensor.py
│       ├── switch.py
│       ├── services.yaml         # Optional service definitions
├── blueprints/
│   └── plant_monitoring.yaml     # Core automation blueprint
├── plants/
│   └── citrus_backyard_spring2025.json
├── cultivars/
│   └── citrus.json               # Generic cultivar profiles
├── runs/
│   └── greenhouse_leafygreens_2025.json
├── automations/
│   └── citrus_backyard_spring2025.yaml
├── input_booleans/
│   └── mode_toggle.yaml
├── scripts/
│   └── daily_threshold_recalc.py  # AI-based threshold recalculation script
├── plant_registry.json          # Central registry of plant metadata
├── .github/workflows/
│   └── validate.yaml             # CI workflow for YAML validation
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

### CI Pipeline Details

The provided GitHub Actions workflow located at `.github/workflows/validate.yaml` ensures:

* YAML files are validated using `yamllint`.
* Home Assistant configurations are verified with `hass --script check_config`.

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
