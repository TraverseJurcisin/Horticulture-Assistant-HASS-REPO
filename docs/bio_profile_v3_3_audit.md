# Audit: Horticulture Assistant Alignment with BioProfile v3.3

## Overview
This audit captures the current state of the BioProfile v3.3 implementation and the surrounding Home Assistant integration. The findings highlight what is complete today, which areas are partially realized, and where additional engineering work is required to reach the intended experience.

## BioProfile v3.3 Structure
### Completed
- Species, cultivar, and line profiles form a three-tier inheritance hierarchy with correct fallback behaviour for unset values.
- Base species definitions supply shared defaults so cultivars and lines only need to override the parameters that differ.

### Partial
- Provenance metadata exists internally, but the UI and logs do not consistently surface whether a value is inherited or overridden.
- Override tracking stops at the first override, making it hard to see the full chain (species → cultivar → line) when multiple layers adjust the same attribute.

### Missing
- Some profile attributes lack proper fallback handling, leaving edge cases where values are not inherited as expected.
- There is no robust, user-facing way to show provenance history (who overrode what and when) beyond internal tags.

## Schema Definitions and Validation
### Completed
- Schemas exist for BioProfiles, yield snapshots, event logs, nutrient logs, and metadata, providing core field validation.
- Numeric ranges (e.g., moisture, pH) and required fields are enforced during input, preventing malformed records from loading.

### Partial
- Cross-validation between profiles, sensors, and logs is limited—missing or unit-mismatched sensors can slip through setup.
- Some relationships (e.g., nutrient logs aligning with nutrient schedules) rely on manual user diligence instead of automated checks.

### Missing
- Metadata schemas are underutilised, and references between entities (profile IDs, sensor IDs) are not validated end-to-end.
- Schema evolution tooling is thin, so incompatible changes are hard to flag ahead of runtime failures.

## Analytics and Stats
### Completed
- Environmental analytics compute core metrics such as VPD, min/max thresholds, and basic condition flags per profile.
- Yield snapshots can be recorded, enabling total yield aggregation for individual profiles.

### Partial
- Aggregated yield metrics (e.g., per species or per square metre) exist in stubs but are not fully surfaced in the UI.
- Historical rollups require manual queries; there is no automated presentation of multi-profile summaries.

### Missing
- Long-term trend tracking and dashboards (charts, comparisons, anomaly detection) are not implemented.
- Predictive analytics or machine-learning driven insights are out of scope in the current codebase.

## Edge/Cloud Synchronisation and Offline Support
### Completed
- Cloud sync scaffolding is present with API clients capable of pushing and pulling profiles, logs, and metadata.
- Authentication flows use tenant-aware tokens, establishing the foundation for segregated cloud data.

### Partial
- Offline edits are not queued for later sync; intermittent connectivity can result in lost updates without user awareness.
- Tenant handling assumes a single context per Home Assistant instance, leaving multi-tenant edge cases to the cloud backend.

### Missing
- Conflict resolution strategies beyond last-write-wins are absent, risking data loss during concurrent edits.
- Feature-tier enforcement and robust offline job queues are not yet implemented.

## Home Assistant Integration Details
### Completed
- BioProfiles register as Home Assistant devices with grouped sensor and binary sensor entities representing thresholds and derived metrics.
- Config and options flows cover initial setup, sensor linkage, and core profile editing without YAML.

### Partial
- UI hints for provenance are minimal, and advanced profile parameters (nutrient schedules, staged targets) remain outside the options flow.
- Some sensor types lack first-class handling, requiring manual configuration or customisation.

### Missing
- Unit conversions, richer diagnostics for misconfigured sensors, and device automation triggers are not yet provided.
- Custom Lovelace cards or dashboards tailored to the integration are still aspirational.

## Monetisation Readiness
### Completed
- Cloud authentication uses API keys/tokens with tenant scoping, preparing the system for subscription-aware services.
- RBAC concepts are acknowledged in the architecture, allowing the cloud backend to enforce access levels.

### Partial
- Client-side feature gating is rudimentary; the integration largely trusts the cloud to reject unauthorised calls.
- Tenant isolation is single-context, limiting shared installations or differentiated local roles.

### Missing
- In-app messaging around account tiers, limits, or upsell paths is absent.
- There is no handling for tier limits (e.g., maximum profiles) beyond server-side rejection.

## Documentation Coverage
### Completed
- A README introduces the integration, outlines setup, and explains the BioProfile hierarchy at a high level.
- Component subdirectories contain targeted READMEs for datasets, scripts, and data catalogues.

### Partial
- Documentation trails current features: provenance visibility, cloud sync behaviour, and advanced analytics lack thorough explanation.
- UI-first configuration steps are described briefly but without detailed walkthroughs or screenshots.

### Missing
- Architectural diagrams, worked examples, and troubleshooting guides are not yet documented.
- Installation guidance for HACS/manual users and clear statements about limitations or roadmap items remain to be added.

## Prioritised Engineering Tasks
1. Expose profile value provenance in the UI so users can tell inherited values from overrides.
2. Strengthen schema cross-validation, ensuring referenced sensors exist and match expected units.
3. Add offline caching/queuing for cloud sync to preserve changes during outages.
4. Extend config and options flows to cover advanced profile parameters such as nutrient schedules.
5. Ship device triggers and automation templates for common plant-care workflows.
6. Expand analytics with yield-per-area metrics, multi-plant summaries, and rolling trend storage.
7. Implement client-side monetisation checks and messaging for feature tiers.
8. Improve error handling with clear user-facing notifications for sensor issues and sync failures.
9. Refresh documentation and inline help to describe all services, sensors, and profile fields.
10. Develop dedicated Lovelace cards or panels that showcase key plant metrics and provenance indicators.

## README Improvement Suggestions
- **Add an architecture overview:** Describe the edge/cloud split, BioProfile inheritance, and data flows using diagrams or structured prose.
- **Document UI-based setup:** Provide a walkthrough of the Home Assistant config and options flows, replacing deprecated YAML examples.
- **Explain cloud sync and offline mode:** Detail how to connect to the cloud, what data is synchronised, and how the system behaves when offline.
- **Showcase profile inheritance:** Include concrete examples (tables or JSON snippets) demonstrating how species, cultivars, and lines interact.
- **Detail available schemas and logs:** Highlight what users can record (yield, events, nutrients) and how those entries feed analytics.
- **Outline analytics and metrics:** Summarise computed values (VPD, condition flags) and note upcoming enhancements.
- **Clarify monetisation:** Communicate account tiers, optional premium features, and how the integration handles feature access.
- **Add developer notes:** Document repository layout, testing commands, and contribution guidelines for prospective contributors.
- **Include visuals:** Add screenshots of the integration in Home Assistant and any custom dashboards to set expectations.
- **Clarify installation methods:** Provide explicit instructions for HACS or manual installation, including repository URLs and directory paths.
