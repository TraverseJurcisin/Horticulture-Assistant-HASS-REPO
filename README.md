![Horticulture Assistant logo](custom_components/horticulture_assistant/logo.jpg)

# Horticulture Assistant for Home Assistant

Horticulture Assistant is a local-first companion for growers who want to coordinate plant monitoring, nutrition, and irrigation inside Home Assistant without relying on cloud APIs. The project ships opinionated defaults, extensive reference data, and optional AI/automation hooks while remaining fully usable offline.

## Vision at a Glance

- **One integration, many growing styles.** Manage greenhouse crops, container gardens, or hydroponic systems by creating per-plant (or per-zone) profiles that live on disk as JSON.
- **Local-first datasets.** Everything from fertilizer registries to stage-based light targets is bundled under `custom_components/horticulture_assistant/data/`. You can version control these files or replace them with your own.
- **Composable services.** Optional AI helpers, irrigation planners, and data exporters sit behind Home Assistant services so you can opt-in incrementally.
- **Friendly to dashboards.** Exposes card-ready sensor metrics (dew point, VPD, DLI) and binary environment checks so you can build rich Lovelace views or drive automations.

## How the Repository is Organized

| Area | Purpose | Where to learn more |
|------|---------|---------------------|
| Integration code | Coordinator, config/option flows, entities, services | [Component internals](custom_components/horticulture_assistant/README.md) |
| Data catalogue | Fertilizer/product schemas, crop targets, irrigation tables | [Data README](custom_components/horticulture_assistant/data/README.md) |
| Fertilizer dataset | Detail/index shards, schema history, validation workflow | [Fertilizer dataset](custom_components/horticulture_assistant/data/fertilizers/README.md) |
| Local working data | User profiles, overrides, cached assets | [Local data](custom_components/horticulture_assistant/data/local/README.md) |
| Scripts | Validation and migration helpers | [Scripts overview](scripts/README.md) *(create your own notes here)* |

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
4. Link sensors, explore the generated device, and customize profile thresholds by editing the JSON in `custom_components/horticulture_assistant/data/local/profiles/`.

For detailed guidance on data structures, file formats, or extending the integration, follow the Readmes linked above.

## Developing & Contributing

- Install dev dependencies: `pip install -r requirements.txt -r requirements_test.txt`
- Run tooling: `pre-commit run --all-files`, `ruff check .`, `hassfest`, `pytest -q`
- Keep fertilizer detail files aligned with the V3e schema using `python scripts/validate_fertilizers_v3e.py`

Pull requests are welcome—especially improvements to the bundled datasets or additional profile automation helpers.

## Licensing & Attribution

Horticulture Assistant is released under the MIT License. Inspiration for the thresholds and card-friendly entities comes from community projects like `homeassistant-plant`, OpenPlantbook, and the Flower Card; documentation links are provided in the component README.
