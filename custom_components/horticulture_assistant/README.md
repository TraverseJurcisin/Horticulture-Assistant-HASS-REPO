# Component Internals

This directory contains the Home Assistant integration for Horticulture Assistant. The code is organised so that profiles, coordinators, and services remain modular and easy to extend.

## Module Overview

| Module | Purpose |
|--------|---------|
| `__init__.py` | Handles config-entry setup, stores references to the profile store, and forwards platforms. |
| `manifest.json` | Home Assistant metadata: domain, version, and ownership details. |
| `config_flow.py` | User flow (minimal) and Options flow that allows users to add profiles, clone thresholds, and wire sensors. |
| `profile_store.py` | Local-first JSON store that persists profile documents under `config/custom_components/horticulture_assistant/data/local/profiles/`. |
| `coordinator.py` | Base DataUpdateCoordinator that computes core metrics (dew point, VPD, etc.). |
| `sensor.py`, `binary_sensor.py`, `number.py` | Surface calculated values and advisory run-time numbers for dashboards and automations. |
| `helpers/calc.py` | Pure functions used by coordinators and tests. |
| `services.yaml` | Declares service signatures (e.g., `create_profile`) that map to service handlers. |
| `diagnostics.py` | Returns a redacted snapshot of configured profiles for the Diagnostics panel (planned extensions). |

## Data Flow

1. Profiles are created through the options flow or by editing JSON under `data/local/profiles/`.
2. `ProfileStore` reads the JSON and hands profiles to coordinators.
3. Coordinators gather sensor values, compute derived metrics, and update entities.
4. Entities publish card-friendly metrics and binary state for dashboards or automations.
5. Services and scripts (e.g., fertilizer validation) provide optional automation hooks.

## Extending the Integration

- **New metrics**: add helper functions in `helpers/calc.py`, surface them via the coordinator, then expose in `sensor.py`.
- **Irrigation advisory logic**: update the coordinator or create dedicated planners that write to the advisory number entity.
- **Profile schema fields**: update the profile store, tests, and the relevant data docs in `data/`.
- **AI/Irrigation services**: bind functions in `services.py` (planned) to Home Assistant service descriptions in `services.yaml`.

Be sure to run `pre-commit run --all-files`, `ruff check .`, and `pytest -q` after changes to keep the integration healthy.
