# Audit: Horticulture Assistant Alignment with BioProfile v3.3

## Overview
This re-audit summarizes the current alignment between the Horticulture Assistant integration and the BioProfile v3.3 architecture. It focuses on profile inheritance, schema coverage, analytics, resolver behavior, cloud readiness, and Home Assistant integration depth following the latest development cycle.

## Findings
### Hierarchical Profile Inheritance and Provenance
- BioProfiles now support hierarchical inheritance spanning species, cultivar, and individual line levels.
- Each profile dynamically resolves missing values from its declared parent, ensuring changes at the species level cascade to cultivars and lines without manual duplication.
- Threshold provenance is captured for every resolved value and is now exposed through HTTP APIs, diagnostics sensors, and a dedicated `profile_provenance` service so users can see inherited versus overridden targets directly inside Home Assistant.

### Schema Definitions and Data Validation
- BioProfile JSON payloads are organized into structured sections (environment, nutrients, etc.) that match the v3.3 schema definitions.
- All profile, nutrient, event, and harvest datasets are stored as JSON and validated against versioned schemas during load and in CI.
- Logging is backed by schemas for yield snapshots and growth events, and the new run summariser builds queryable lifecycle records without introducing a separate run object.

### Statistics Computation and Aggregation
- Environmental analytics are computed per profile, including averages for VPD, dew point, temperature, humidity, and other linked sensor metrics.
- Yield snapshots drive cumulative harvest statistics and yield-per-area calculations when profile metadata includes growing area.
- Success-rate metrics are computed from run logs with weighted per-profile averages and contributor metadata, and species-level rollups combine cultivar and species histories for portfolio-wide benchmarking.
- Run lifecycle summaries aggregate duration, success, and yield information for each cultivation run and are now available via HTTP, services, and diagnostic sensors alongside the success analytics.
- Success-rate analytics are surfaced to the local API and Home Assistant via HTTP summaries, enriched service responses, and dedicated success-rate sensors that expose contributor weights and stress data.

### Local Resolver Capabilities (Value Resolution)
- The resolver assembles a resolved dataset at runtime by recursively merging inherited values, avoiding static copies of defaults.
- Target metadata tracks the source of each resolved value, laying the groundwork for UI indicators that show whether data is inherited or overridden.
- Updates to parent profiles flow through the inheritance chain unless explicitly overridden, simplifying lifecycle management of default settings.

### Edge-to-Cloud Sync and API Connectivity
- Early-stage cloud/edge infrastructure exists under the `cloud/` module, including tenant-aware payload handling and preliminary sync logic.
- Backend scaffolding recognizes user/tenant IDs and includes initial RBAC hooks, preparing for role-based feature gating.
- Home Assistant now exposes a cloud login/logout/refresh workflow that persists access tokens, updates sync configuration, and drives a cloud connection diagnostic sensor.
- Cloud authentication flows persist available organizations, track selected org/role metadata, and expose a new `cloud_select_org` service plus HTTP diagnostics so operators can pivot between tenants without reauthenticating.

### Home Assistant Integration Depth
- Each BioProfile is surfaced as a Home Assistant device with sensor and binary sensor entities for resolved thresholds and derived analytics such as dew point and VPD.
- Dedicated success-rate sensors expose the most recent cultivation outcomes, a provenance diagnostic sensor summarises inherited versus overridden targets, and new run-status sensors capture lifecycle health while a cloud connection sensor reports sync posture.
- Config and options flows allow users to create profiles, clone defaults, attach sensors, and adjust thresholds directly within Home Assistant, and the cloud login flow is now available from services with persistent token storage.
- Additional polishing opportunities include enhancing device info and expanding history/analytics cards as the new provenance and run data is incorporated into dashboards.

### Multi-Tenant Backend Readiness
- Cloud-bound operations are scoped by tenant identifiers, providing the foundation for multi-tenant isolation.
- RBAC support is wired into backend scaffolding, though UI-driven organization management and advanced sharing controls are not yet available.
- Cloud schema hooks exist for shaping edge payloads, but hosted APIs, login flows, and conflict resolution still need to be completed before launch.
- Organization-aware headers are now propagated through the edge store, worker, sensors, and HTTP APIs, ensuring per-org caches and diagnostics stay isolated ahead of full multi-tenant administration tooling.

### What’s Implemented vs. Missing
- Hierarchical inheritance, schema validation, per-profile analytics (including success-rate aggregation and run summaries), and comprehensive Home Assistant entity coverage are implemented and functioning.
- Provenance indicators, richer dashboards for aggregated analytics, deeper run lifecycle tooling (e.g., phase planning), full cloud sync, and multi-tenant administration remain outstanding tasks.

## Updated Engineering Task List
The following task backlogs capture the remaining work areas identified by the audit.

### Backend
- Finalize cloud sync implementation, covering API endpoints, two-way data exchange, conflict resolution, and offline caching.
- Harden the new cloud authentication services with MFA, refresh scheduling, and UI integration for token lifecycle management.
- Implement organization support for multi-tenant deployments so profiles and users can be grouped with shared access policies.
- Enforce and validate RBAC rules across cloud operations to respect roles such as admin and grower.
- Expand success-rate exposure to cloud endpoints and UI dashboards, building on the new local API summaries and service responses.
- Enable species-level and cultivar-level rollup statistics for local dashboards and future cloud reporting.
- Enhance event and harvest logging to support discrete grow “runs” or crop cycles with queryable storage.
- Integrate the fertilizer and nutrient datasets into profile management for logging nutrient applications with schema validation.
- Implement optional AI or automation hooks (e.g., irrigation scheduling, setpoint optimization) with appropriate monetization controls.

- Integrate the cloud login/logout workflow into the Home Assistant UI and surface sync status indicators alongside the new diagnostic sensors.
- Display aggregated statistics and history within Home Assistant, such as cards for yield trends, average VPD over time, and the new success-rate rollups.
- Refine device information to highlight species and cultivar context within the device panel.
- Ensure new sensor and binary sensor entities carry complete metadata (units, icons, categories) and are documented for end users.
- Stress-test multi-profile deployments to confirm coordinators scale and UI responsiveness is maintained.
- Improve the options flow experience with utilities like cloning wizards or batch sensor assignment tools.
- Update public documentation to explain new features, logging workflows, cloud setup expectations, and monetization plans.

## Next Steps
Addressing the backlog items above will complete the BioProfile v3.3 alignment, expose provenance and analytics to users, and prepare the integration for a robust hybrid cloud offering.
