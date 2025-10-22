# Audit: HorticultureAssistant Alignment with BioProfile v3.3

## Overview
This document summarizes an audit of the current HorticultureAssistant codebase against the BioProfile v3.3 specification. The review focuses on structural profile changes, schema completeness, resolver behavior, data normalization, integration capabilities, and architectural readiness for hybrid cloud deployment.

## Findings
### BioProfile Structure & Inheritance
- The application relies on a single `PlantProfile` model without distinct species and cultivar representations.
- No inheritance or linkage exists that would allow cultivars to reuse or override species attributes.

### Schema Definitions
- Only the legacy plant profile schema is available; new BioProfile schema concepts are absent.
- Models for cultivation run events, harvest events, computed statistics, and Home Assistant resolver configuration are missing.

### Terminology Usage
- Deprecated "Plant Profile" terminology is still present throughout the codebase. The updated "BioProfile" naming convention is not adopted.

### Local Resolver & Provenance
- No resolver exists to merge parent and child profile data or track provenance of inherited values. The absence of hierarchical profiles prevents provenance metadata from being recorded.

### Yield Densitization & Aggregation
- Harvest and yield tracking is not implemented, so there is no densitization (e.g., kg/m²) or aggregation at the species level.

### Cloud/Edge Synchronization
- The project lacks any synchronization workflow or service for exchanging data with a cloud backend, leaving deployments edge-only.

### Home Assistant Integration
- There is no automated pipeline that exposes resolved profile data or statistics to Home Assistant through sensors or configuration outputs.

### Monetizable Centralization Architecture
- The repository is geared toward a single-tenant experience. It lacks multi-tenant isolation, TimescaleDB-backed telemetry storage, and granular role-based access control necessary for a SaaS deployment.

## Recommended Engineering Tasks
```json
[
  {
    "task": "Implement hierarchical BioProfile model (species & cultivar)",
    "details": "Introduce separate classes for SpeciesProfile and CultivarProfile, with CultivarProfile inheriting from SpeciesProfile (or sharing a base class). Update the data model to link each CultivarProfile to its parent SpeciesProfile and migrate existing PlantProfile data."
  },
  {
    "task": "Update schema definitions for events and stats",
    "details": "Define schemas/models for Run events and Harvest events, capturing planting start/end dates and yield outputs. Add support for computed statistics at the profile or run level and generate database migrations."
  },
  {
    "task": "Rename and refactor deprecated 'Plant Profile' terminology",
    "details": "Replace all references of 'PlantProfile' with 'BioProfile' terminology in code, tests, and documentation."
  },
  {
    "task": "Develop local resolver for profile inheritance with provenance",
    "details": "Implement a resolver that merges species and cultivar data, applies overrides, and annotates each field with provenance metadata. Integrate the resolver into data access layers."
  },
  {
    "task": "Add yield densitization and species-level aggregation",
    "details": "Extend the Harvest event schema to record yield quantity and growing area, calculate normalized yields (kg/m²), and aggregate statistics at the species level."
  },
  {
    "task": "Implement cloud/edge data synchronization mechanism",
    "details": "Create a synchronization service or background jobs that replicate data between the local edge deployment and a central cloud API, including conflict resolution strategies."
  },
  {
    "task": "Integrate with Home Assistant for sensor data",
    "details": "Expose resolved profile values and statistics to Home Assistant via REST endpoints or generated configuration files and document how to enable the integration."
  },
  {
    "task": "Prepare architecture for multi-tenant cloud and RBAC",
    "details": "Refactor the application for multi-tenant operation, adopt PostgreSQL/TimescaleDB for telemetry, and implement role-based access controls with clearly defined user roles."
  }
]
```

## Next Steps
Addressing the tasks above will bring the project in line with BioProfile v3.3 expectations, enabling hierarchical profile management, advanced analytics, cloud synchronization, and integration with Home Assistant within a monetizable, multi-tenant architecture.
