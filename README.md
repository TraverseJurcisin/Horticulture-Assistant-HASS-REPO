# BETA – UNDER ACTIVE DEVELOPMENT

# Horticulture Assistant for Home Assistant

> **Status:** Functional beta. The core profile store, data catalogue, and Home Assistant integration are ready for day-to-day experimentation, but the data model and UI may still shift as upcoming logging and cloud features land.

Horticulture Assistant is a local-first companion for growers who want to coordinate plant monitoring, nutrition, and irrigation inside Home Assistant without relying on cloud APIs. The project ships opinionated defaults, extensive reference data, and optional AI/automation hooks while remaining fully usable offline.

## Vision at a Glance

- **One integration, many growing styles.** Manage greenhouse crops, container gardens, or hydroponic systems by creating per-plant (or per-zone) profiles that live on disk as JSON.
- **Local-first datasets.** Everything from fertilizer registries to stage-based light targets is bundled under `custom_components/horticulture_assistant/data/`. You can version control these files or replace them with your own.
- **Composable services.** Optional AI helpers, irrigation planners, and data exporters sit behind Home Assistant services so you can opt-in incrementally.
- **Friendly to dashboards.** Exposes card-ready sensor metrics (dew point, VPD, DLI) and binary environment checks so you can build rich Lovelace views or drive automations.

## Profile Hierarchy & Local Data Model

Profiles inherit defaults through a three-tier hierarchy that mirrors BioProfile v3.3:

1. **Species profiles** define canonical defaults (e.g., tomato temperature, humidity, and light targets).
2. **Cultivar profiles** refine those defaults for specific cultivars or varieties.
3. **Line profiles** represent the individual plant, bed, or zone you add in Home Assistant.

When a value is missing at the line level, the resolver automatically falls back to the cultivar, then the species. This keeps profile files concise while ensuring every sensor and threshold has a usable value.

### Example line profile JSON

```jsonc
{
  "id": "alicante_tomato_north_bed",
  "display_name": "Alicante Tomato – North Bed",
  "species": "solanum_lycopersicum",
  "cultivar": "alicante",
  "area_sq_m": 1.2,
  "overrides": {
    "environment": {
      "temperature": {
        "min_c": 19.5,
        "max_c": 28.0
      },
      "humidity": {
        "min_percent": 55
      }
    }
  }
}
```

- The `species` and `cultivar` fields link to reference profiles in `custom_components/horticulture_assistant/data/`.
- Only overridden values appear under `overrides`; everything else is inherited.
- Optional metadata such as `area_sq_m` enables future metrics (e.g., yield per square metre).

### Working with overrides

1. Create a new profile through **Configure → Options → Add profile**.
2. Inspect the generated JSON under `custom_components/horticulture_assistant/data/local/profiles/`.
3. Use the **Clone thresholds** action in the options flow if you want to materialise inherited values for editing.
4. Remove a key from the JSON to fall back to cultivar/species defaults; save and reload the integration to apply changes.

## How the Repository is Organized

| Area | Purpose | Where to learn more |
|------|---------|---------------------|
| Integration code | Coordinator, config/option flows, entities, services | [Component internals](custom_components/horticulture_assistant/README.md) |
| Data catalogue | Fertilizer/product schemas, crop targets, irrigation tables | [Data README](custom_components/horticulture_assistant/data/README.md) |
| Fertilizer dataset | Detail/index shards, schema history, validation workflow | [Fertilizer dataset](custom_components/horticulture_assistant/data/fertilizers/README.md) |
| Local working data | User profiles, overrides, cached assets | [Local data](custom_components/horticulture_assistant/data/local/README.md) |
| Scripts | Validation and migration helpers | [Scripts overview](scripts/README.md) *(create your own notes here)* |

## Reference Data Highlights

- **Crop targets:** Stage-based VPD, temperature, humidity, and light recommendations for dozens of food and ornamental crops.
- **Fertilizer catalogue:** NPK analyses, micronutrient profiles, and application notes validated against the `v3e` fertilizer schema (`scripts/validate_fertilizers_v3e.py`).
- **Irrigation & care tables:** Starter schedules for irrigation frequency, EC/PPM targets, and disease risk cues.
- **Metadata registries:** Controlled vocabularies for growth stages, substrate types, and measurement units that keep profiles and logs consistent.

## High-Level Architecture

1. **Profile store** – a simple JSON-backed directory that holds your plant profiles (`profile_store.py`).
2. **Coordinators & entities** – DataUpdateCoordinators read linked sensors, compute metrics, and expose sensor/binary/number entities under each profile device.
3. **Options flow** – Use Home Assistant’s “Configure” action to add profiles, clone thresholds, or wire sensors without editing YAML.
4. **Reference datasets** – Fertilizer, pest, environment, and irrigation tables power future automation hooks. These live alongside schemas so CI can validate contributions.
5. **Services & automation hooks** – Advisory number entities, service stubs, and exporters let you bolt on irrigation schedulers or AI setpoint generators when needed.

## Getting Started (Very Short Version)

1. Copy the repository into your Home Assistant configuration under `custom_components/horticulture_assistant/`.
2. Restart Home Assistant and add “Horticulture Assistant” via **Settings → Devices & Services → Add Integration**.
3. From the integration card, open **Configure → Options → Add profile** to create your first plant or zone.
4. Link sensors, explore the generated device, and customise thresholds by either editing the JSON under `custom_components/horticulture_assistant/data/local/profiles/` or adjusting the exposed number entities in the Home Assistant UI.
5. (Optional) Version control the `data/local/` directory so you can track profile tweaks alongside your automation code.

For detailed guidance on data structures, file formats, or extending the integration, follow the Readmes linked above.

## Example Automations & Dashboards

- **Alert when conditions drift:** Trigger a notification when `binary_sensor.<profile>_temperature_ok` turns off, then use the accompanying temperature sensors to diagnose the issue.
- **Water-on-demand:** Combine `binary_sensor.<profile>_moisture_ok` with a smart valve switch to deliver irrigation only when moisture drops below your thresholds.
- **Lovelace snapshot:** Pair sensors such as `sensor.<profile>_vpd`, `sensor.<profile>_dew_point`, and `sensor.<profile>_dli` with a plant photo card for a quick climate health overview.

## Entitlements & Feature Availability

Some automation helpers rely on premium capabilities. The integration derives *entitlements* from the account roles and organisation context returned by the optional cloud service. When an entitlement is missing, the related service responds with a clear error instead of failing silently.

- **Always available:** Local profile management, environment metrics, nutrient/cultivation logging, and manual threshold editing remain usable offline with no subscription.
- **AI assistance:** Services such as `run_recommendation` and AI-driven profile generation require the **AI assistance** entitlement. Acquire it by logging into a cloud account with an `ai`, `premium`, or `pro` role, or by manually listing `ai_assist` under `cloud_feature_flags` in advanced setups.
- **Irrigation automation:** Watering recommendations and the `apply_irrigation_plan` bridge need the **irrigation_automation** entitlement. Cloud roles like `irrigation` or `premium` grant this, while free users see a descriptive Home Assistant error when calling the service.
- **Organisation administration:** Cloud-managed teams expose multi-tenant tooling only when the active organisation role is elevated (e.g., admin/manager). Attempting those flows without the entitlement returns a guidance error rather than altering configuration.

The current entitlements are exposed in diagnostics (cloud connection sensors and the `profile_provenance` service response). This makes it easy to audit which premium tiers are active and ensures free installs continue operating gracefully.

## Lifecycle & Yield Tracking

- **Capture cultivation milestones:** Call the `record_cultivation_event` service to log inspections, pruning, transplanting, or custom milestones. Logged events immediately update the diagnostic **Event Activity** sensor with totals, last-event metadata, and tag breakdowns.
- **Harvest history made visible:** `record_harvest_event` continues to append harvests while now feeding the **Yield Total** sensor. The sensor exposes cumulative grams harvested, average yield per harvest, density metrics, and contributor weights for species rollups.
- **Nutrient cadence at a glance:** The **Feeding Status** sensor reflects nutrient applications recorded via `record_nutrient_event`, including the days since the last feeding and product usage summaries, making it easy to keep irrigation schedules on track.
- **Species rollups:** All cultivation, nutrient, and harvest events aggregate to the species profile so you can compare cultivars and monitor organisation-wide cadence without leaving Home Assistant.
- **Cloud-ready statistics:** Enabling cloud sync now streams the latest computed yield, nutrient, and event snapshots (with per-entity vector clocks) so remote dashboards and APIs stay in lockstep with the on-prem analytics.

## Developing & Contributing

- Install dev dependencies: `pip install -r requirements.txt -r requirements_test.txt`
- Run tooling: `pre-commit run --all-files`, `ruff check .`, `hassfest`, `pytest -q`
- Keep fertilizer detail files aligned with the V3e schema using `python scripts/validate_fertilizers_v3e.py`

Pull requests are welcome—especially improvements to the bundled datasets or additional profile automation helpers.

## Roadmap & Upcoming Enhancements

- **Cloud sync (optional):** Opt-in remote access, organisation sharing, and AI helpers while keeping local-first operation the default.
- **Organisation controls:** Multi-tenant role management and premium feature toggles for growers who manage multiple sites or teams.
- **Advanced analytics:** Season-over-season comparisons, species health dashboards, and automated insight generation on top of the new event and yield datasets.

Progress on these items will be announced in release notes; expect schema tweaks as they roll out.

## Licensing & Attribution

Horticulture Assistant is released under the MIT License. Inspiration for the thresholds and card-friendly entities comes from community projects like `homeassistant-plant`, OpenPlantbook, and the Flower Card; documentation links are provided in the component README.
