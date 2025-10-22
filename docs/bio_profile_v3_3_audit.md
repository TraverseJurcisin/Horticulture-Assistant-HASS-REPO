# Audit: HorticultureAssistant Alignment with BioProfile v3.3

## Overview
This document captures the latest audit of the Horticulture Assistant Home Assistant integration against the BioProfile v3.3 architecture guidelines. It consolidates observations about profile modeling, schema coverage, resolver behavior, data analytics, integration touchpoints, and readiness for hybrid edge/cloud operation.

## Findings
### BioProfile Structure and Inheritance
- Plant- and zone-level configurations are stored as JSON profiles under `data/local/profiles/`, enabling tailored BioProfiles per cultivar or installation.
- Runtime lineage chains now connect cultivars back to their parent species. Each profile maintains a recorded ancestry chain (`BioProfile.lineage`) and the registry refresh populates species ↔ cultivar links automatically. When species data is updated, child profiles inherit the new values during resolution, eliminating the old copy-once behavior.

### Schema Definitions and Usage
- The fertilizer dataset continues to ship with an explicit JSON schema (validated via `scripts/validate_fertilizers_v3e.py`).
- BioProfile payloads, run histories, harvest histories, and computed statistics now have Draft 2020-12 JSON schemas under `custom_components/horticulture_assistant/data/schema/`. The new `validate_profiles.py` and `validate_logs.py` scripts execute during CI to ensure authored JSON never drifts from the contract, and the schemas are consumed by the validator helper for ad-hoc checks.

### Legacy Terminology Check
- The repository has largely adopted the BioProfile terminology. The deprecated "PlantProfile" naming no longer appears in user-facing documentation or core modules, reducing the risk of confusion.

### Local Resolver Logic and Provenance
- The integration uses Home Assistant `DataUpdateCoordinator` instances to blend live sensor data with profile thresholds, producing derived metrics like VPD, DLI, and dew point.
- Preference resolution now traverses the lineage chain when a source is unset, building provenance-aware `ResolvedTarget` entries annotated with the ancestor profile that supplied each value. Inherited thresholds arrive with an explicit inheritance citation, depth metadata, and the original parent annotation preserved as an overlay.

### Yield Data and Aggregation
- Harvest logging is now first-class: `ProfileRegistry.async_record_harvest_event` captures yield, area, and density details, and the profile dataclass stores both `run_history` and `harvest_history` entries.
- The `profile.statistics.recompute_statistics` module aggregates those events into cultivar- and species-level `YieldStatistic` snapshots (including kg/m², harvest counts, and contributor weights). These snapshots are persisted alongside computed stats and surfaced via the new HTTP API summaries.
- Run log analytics now compute environment rollups. Daily light, VPD, temperature, humidity, and run duration averages are distilled into `environment/v1` computed-stat snapshots for each cultivar and species, giving both local dashboards and cloud pipelines a structured view of growing conditions.

### Environmental Analytics and Provenance
- Environment snapshots expose contributor weights per cultivar, letting species-level analytics show which cultivars provided the underlying telemetry and how many runs informed the averages.
- The authenticated HTTP endpoints return both yield and environment computed stats, so external dashboards receive provenance-rich payloads without touching the Home Assistant entity registry.

### Edge-to-Cloud Sync Capability
- The add-on ships an opt-in cloud sync subsystem (`custom_components.horticulture_assistant.cloudsync`) featuring an outbox/inbox SQLite store, NDJSON event protocol, bidirectional worker, and status sensors. Cloud connectivity can be configured via the options flow (tenant, endpoint, and device token) and the worker reconciles cloud snapshots with local overrides when enabled.
- By default the integration still operates offline-only; sites that do not configure the sync options remain local-first.

### Home Assistant Integration (Sensors & Config)
- The custom integration follows Home Assistant best practices by exposing resolved thresholds and computed stats as entities tied to a profile-specific device. Users can link existing sensors via the config flow, and the coordinator refreshes those entities without requiring external REST sensors.
- A new authenticated HTTP surface (`/api/horticulture_assistant/profiles/...`) returns full BioProfile payloads, yield summaries, and provenance metadata so external dashboards can consume the knowledge graph without scraping the entity registry.
- HTTP responses now bundle all computed-stat snapshots (yield and environment) so consumers can trend conditions, yields, and inheritance metadata from a single fetch.

### Cloud/Multitenancy and Monetization Readiness
- A draft multi-tenant schema (`cloud/ddl/cloud_schema.sql`) and cloud-edge architecture blueprint document the path to hosted services, and the edge sync client already understands tenant IDs and device credentials.
- Role-based access control, user onboarding flows, and hosted APIs remain future work, but the new HTTP API and schema contracts give the backend concrete payloads to target when those services materialize.

## Recommended Engineering Tickets
```json
[
  {
    "title": "Stress-test Hierarchical Profile Inheritance",
    "description": "Exercise the lineage builder against deep cultivar chains, shared templates, and partially missing ancestors. Add regression fixtures containing stored lineage payloads to guarantee backward compatibility across migrations.",
    "files": [
      "custom_components/horticulture_assistant/profile/utils.py",
      "tests/test_profile_registry.py",
      "tests/test_sources.py"
    ]
  },
  {
    "title": "Apply JSON Schema Validation at Runtime",
    "description": "Wire the new schemas into profile loading/saving so malformed run or harvest entries raise issues immediately. Emit Home Assistant repairs for invalid payloads and block persistence when the schema contract is broken.",
    "files": [
      "custom_components/horticulture_assistant/profile_store.py",
      "custom_components/horticulture_assistant/validators.py",
      "custom_components/horticulture_assistant/diagnostics.py"
    ]
  },
  {
    "title": "Surface Inheritance Provenance in the UI",
    "description": "Expose the inheritance metadata on Lovelace cards and diagnostics, including the parent profile name, depth, and source annotation for every resolved target.",
    "files": [
      "custom_components/horticulture_assistant/sensor.py",
      "custom_components/horticulture_assistant/diagnostics.py",
      "custom_components/horticulture_assistant/dashboard/"
    ]
  },
  {
    "title": "Harden the HTTP Profile API",
    "description": "Add token/role gating, pagination, and field filtering for the new `/api/horticulture_assistant/profiles` endpoints so large installations and future cloud consumers can query safely.",
    "files": [
      "custom_components/horticulture_assistant/http.py",
      "custom_components/horticulture_assistant/config_flow.py",
      "custom_components/horticulture_assistant/const.py"
    ]
  },
  {
    "title": "Enhance Cloud Sync Telemetry and Conflict Reporting",
    "description": "Publish metrics for upload latency, conflict resolutions, and queue depth through both sensors and diagnostics to help operators monitor hybrid deployments.",
    "files": [
      "custom_components/horticulture_assistant/cloudsync/edge_worker.py",
      "custom_components/horticulture_assistant/cloudsync/edge_store.py",
      "custom_components/horticulture_assistant/sensor.py"
    ]
  },
  {
    "title": "Design RBAC-backed Cloud Onboarding",
    "description": "Connect the edge sync client and HTTP API with a future hosted backend by defining user roles, device enrollment flows, and secure token rotation policies.",
    "files": [
      "cloud/api/",
      "custom_components/horticulture_assistant/config_flow.py",
      "docs/cloud_edge_architecture.md"
    ]
  }
]
```

## Next Steps
Executing the tickets above will close the identified BioProfile v3.3 gaps, modernize profile management, enable rigorous data validation, and lay the groundwork for analytics, cloud connectivity, and eventual SaaS monetization.
