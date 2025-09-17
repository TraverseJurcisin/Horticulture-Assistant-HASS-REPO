# Horticulture Assistant for Home Assistant

> Build data-driven digital twins of every plant you care for and let Home Assistant keep an eye on light, climate, irrigation, and nutrition – with optional AI helpers when you need a second opinion.

## Highlights
- **Per-plant profiles** with stage-aware thresholds, derived metrics, and historical context stored locally as JSON.
- **Sensor linking** for temperature, humidity, CO2, PAR/DLI, soil moisture, EC, irrigation flow, and more.
- **Derived horticulture analytics** including VPD, DLI, dew point, mold risk index, nutrient balance, and irrigation summaries.
- **Optional AI workflows** to suggest setpoints, irrigation plans, and recommendations that you can approve before applying.
- **Automation hooks** that push run-times to external schedulers (OpenSprinkler, Irrigation Unlimited) or custom automations.
- **Diagnostics and export tools** for quick support snapshots, profile backups, and reproducible experiments.

## Requirements
- Home Assistant 2023.12 or newer.
- Local or remote sensors that expose the data you want to track (temperature, RH, light, moisture, etc.).
- [HACS](https://hacs.xyz/) is strongly recommended for painless updates (manual install is also supported).
- Optional: API keys for your AI provider or search service if you plan to use the AI modules.

## Installation
### Install via HACS (recommended)
1. In Home Assistant open **HACS ? Integrations ? Three-dot menu ? Custom repositories**.
2. Add `https://github.com/TraverseJurcisin/Horticulture-Assistant-HASS-REPO` and select **Integration**.
3. Search for **Horticulture Assistant** in HACS and install.
4. Restart Home Assistant when prompted.

### Manual install
1. Download the latest release archive from GitHub.
2. Copy `custom_components/horticulture_assistant/` into your Home Assistant config directory (`config/custom_components/`).
3. Restart Home Assistant to load the integration.

## First-run checklist
1. Navigate to **Settings ? Devices & Services ? Add Integration ? Horticulture Assistant**.
2. Create your first profile by naming the plant and (optionally) choosing a template species.
3. Link existing sensors (temperature, humidity, illuminance/PAR, soil moisture, EC, CO2, etc.).
4. Confirm or adjust thresholds for each variable; clone from another profile if you already dialed one in.
5. Enable optional modules:
   - **AI recommendations** by supplying an API key and model in the options flow.
   - **Irrigation planner** by pointing to your automation service or irrigation controller.
6. Entities will appear under the new device for quick access in dashboards or automations.

## Entities and data model
Each profile exposes a consistent set of helpers so dashboards, blueprints, and scripts remain portable.

| Type | Example entity | Purpose |
|------|----------------|---------|
| Sensor | `sensor.tomato_vpd` | Stage-aware vapor pressure deficit in kPa. |
| Sensor | `sensor.tomato_dli` | Daily light integral in mol·m?²·day?¹. |
| Sensor | `sensor.tomato_dew_point` | Dew point temperature for mold risk checks. |
| Binary sensor | `binary_sensor.tomato_environment_ok` | Aggregated state covering light, temperature, humidity, and airflow thresholds. |
| Binary sensor | `binary_sensor.tomato_moisture_ok` | Indicates whether measured soil/EC stays within the target band. |
| Number | `number.tomato_irrigation_runtime_minutes` | Suggested irrigation runtime for the next cycle. |
| Diagnostic sensor | `sensor.tomato_ai_confidence` | Confidence score attached to latest AI recommendation. |

Entities share attributes describing source sensor IDs, configured thresholds, last refresh timestamps, and any pending recommendations.

## Services
All services are discoverable in **Developer Tools ? Services** once the integration is loaded. Highlights include:

- `horticulture_assistant.create_profile`
- `horticulture_assistant.duplicate_profile`
- `horticulture_assistant.delete_profile`
- `horticulture_assistant.update_sensors`
- `horticulture_assistant.generate_profile` (AI/species/template clone)
- `horticulture_assistant.apply_irrigation_plan`
- `horticulture_assistant.export_profile`
- `horticulture_assistant.import_profiles`

The complete schema lives in `services.yaml` if you need payload details for automations.

## Optional modules
### AI copilots
Provide an API key and model name to unlock:
- AI-generated setpoints and nutrient guidelines.
- Summaries of web research (if a search API is configured).
- A manual approval queue so you remain in control of any automatic change.

### Irrigation integration
Use the built-in planners to:
- Calculate runtime suggestions based on ET, crop coefficients, or stage-based thresholds.
- Push schedules directly to controllers via services, or just expose advisory entities to your own automations.

### Dashboards & reports
The `dashboard/` helpers export Grafana and Lovelace-ready JSON so you can ship pre-built dashboards alongside profiles.

## Data storage
Everything is local-first and human-readable:

```
config/
+-- custom_components/horticulture_assistant/
    +-- data/
    ¦   +-- local/               # Your profiles, analytics snapshots, cached datasets
    ¦   +-- fertilizers/         # Fertilizer product index & heavy metal compliance data
    ¦   +-- light/               # Spectrum and crop-stage targets
    +-- analytics/               # Export scripts and utilities
```

Version these files with Git or copy them between Home Assistant instances to replicate a greenhouse configuration.

## Upgrading
1. Update via HACS or copy the latest release files over the existing component.
2. Restart Home Assistant.
3. Visit **Settings ? Devices & Services ? Horticulture Assistant ? Configure** to review any new options.

## Troubleshooting
- Use the **Diagnostics** button on the device page to export a redacted snapshot for support.
- Validate data files with `python -m scripts.validate_profiles` before committing.
- Run `python -m pytest` and `python -m ruff check --fix .` to verify changes locally.
- Enable debug logging by adding the snippet below to `configuration.yaml`:

  ```yaml
  logger:
    default: info
    logs:
      custom_components.horticulture_assistant: debug
  ```

## Development
- Clone the repository and install dependencies with `pip install -r requirements.txt`.
- Run `pre-commit install` then `pre-commit run --all-files` before opening a PR.
- Tests live under `tests/`; run them with `python -m pytest`.
- Typed checks rely on Python 3.11+ features; keep files UTF-8 encoded for CI.

## Contributing & support
Issues and feature requests are tracked at the [GitHub issue tracker](https://github.com/TraverseJurcisin/Horticulture-Assistant-HASS-REPO/issues). Pull requests are welcome—please include tests or sample data when adding features.

## License
Released under the MIT License. See [`LICENSE`](LICENSE) for details.
