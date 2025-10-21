# Cloud-Edge Architecture for Horticulture Assistant

This document details the implementation-ready cloud and edge design that keeps the Home Assistant integration fully offline-capable while unlocking paid, centralized features. It complements the existing local-first datasets and services shipped with the project.

## Goals Recap

- Deliver curated libraries, pooled analytics, and optimization features through a managed cloud service.
- Preserve local autonomy: the Home Assistant add-on must operate end-to-end while disconnected and keep resolving profiles from cached data.
- Avoid data duplication by treating the cloud as the authoritative system of record and the edge as an append-only change producer with read-through caches.

## Topology

```
+-----------------+            Secure Sync (bi-directional)           +------------------+
|  Edge (HA Addon)|  <----------------------------------------------> |  Cloud Service   |
|  - Local DB     |                                                 |  - API + Auth     |
|  - Resolver     | Offline-first: read from local                  |  - Postgres/TSDB  |
|  - Telemetry    | cache; queue outbox when offline                |  - Object Store   |
+-----------------+                                                 |  - Analytics/ML   |
               ^                                                    |  - Materialized   |
               | local sensors/actors                               |    Views/Stats    |
               v                                                    +------------------+
```

## Data Residency

| Data Type | Edge | Cloud |
|-----------|------|-------|
| Species/Cultivar/Line Profiles | Cached snapshots (overrides allowed) | Canonical, curated, versioned |
| Blueprints (zones, bindings, programs) | Authoritative per site | Optional backup & sharing |
| Runs/Batches/Telemetry | Authoritative per site | Aggregation & cross-site analytics |
| Computed Stats | Cached snapshots | Canonical, centrally recomputed |
| User Accounts/Roles/Tenants | Token + tenant cache | Canonical RBAC/ABAC |

Monetization levers include curated libraries, pooled benchmarking, optimization & anomaly detection, secure backups, and a future recipe marketplace.

## Identity & Multi-Tenancy

- Use ULID/UUIDv7 identifiers for all records to allow offline-safe creation and chronological sorting.
- Every record includes `tenant_id` and is protected via Postgres Row-Level Security (RLS).
- Edge devices are registered per tenant and authenticate using device credentials.

## Sync Protocol Overview

Synchronization is event-sourced and tolerant to long offline periods. All changes are expressed as append-only events encoded as NDJSON.

```json
{
  "event_id": "01J8…",
  "tenant_id": "tn_…",
  "device_id": "edge_A",
  "ts": "2025-10-20T12:03:14Z",
  "entity_type": "run|profile|blueprint|telemetry|yield|computed",
  "entity_id": "bp_cultivar_blueberry_tophat_v1",
  "op": "upsert|patch|delete",
  "patch": { "…": "…" },
  "vector": { "device": "edge_A", "counter": 184 },
  "actor": "user_or_service",
  "signature": "ed25519:…",
  "hash_prev": "sha256:…"
}
```

Conflict resolution uses CRDT-style policies:

- **LWW Register** for numeric/scalar values with Lamport/vector clock comparisons.
- **OR-Set** for tag collections.
- **MV Register** for lists/arrays with domain-specific reconciliation.

Edge devices retry uploads until acknowledged. Downstream deltas stream from `/sync/down?cursor=…`.

## Database Footprint

Cloud services rely on PostgreSQL + TimescaleDB plus an object store for large artifacts. Edge devices use SQLite (or the Home Assistant recorder) split between local authoritative data and cached cloud snapshots. See [`cloud/ddl/cloud_schema.sql`](../cloud/ddl/cloud_schema.sql) for the canonical DDL.

## Resolver Responsibilities

Both cloud and edge resolvers follow the same inheritance rules:

1. Load lineage (line → cultivar → species) from local cache.
2. Walk overrides top-down returning the first value found.
3. Apply fallbacks (genus/family, blueprint defaults) if needed.
4. Overlay computed statistics when policy allows data-driven values.
5. Always return provenance metadata with staleness flags.

The reference edge resolver lives in [`custom_components/horticulture_assistant/cloudsync/resolver_service.py`](../custom_components/horticulture_assistant/cloudsync/resolver_service.py).

## Sync Worker (Edge)

The Home Assistant add-on ships an async worker that:

1. Reads new events from the SQLite outbox.
2. POSTs them to `/sync/up` as NDJSON with exponential backoff.
3. Fetches `/sync/down` deltas, applies CRDT policies, and stores refreshed snapshots.
4. Updates health sensors such as `binary_sensor.cloud_connected` and `sensor.cloud_snapshot_age_days`.

Reference implementation: [`custom_components/horticulture_assistant/cloudsync/edge_worker.py`](../custom_components/horticulture_assistant/cloudsync/edge_worker.py).

Home Assistant exposes the sync status through dedicated diagnostics entities:

- `binary_sensor.cloud_connected` — connectivity to the cloud service.
- `binary_sensor.local_only_mode` — true when running in offline fallback.
- `sensor.cloud_snapshot_age_days` — days since the newest cached snapshot.
- `sensor.cloud_outbox_size` — pending events queued for upload.

## Cloud API Surfaces

- **Auth:** OIDC/OAuth2 for users (PKCE) plus device credentials.
- **Profiles:** `GET /profiles/{id}`, `GET /profiles`, `POST/PATCH /profiles` (role-gated).
- **Resolver:** `GET /resolve?profile={id}&field=targets.vpd.vegetative` returning value + provenance.
- **Runs:** `POST /runs/events` for bulk NDJSON ingest; `GET /runs` for retrieval.
- **Stats:** `POST /stats/jobs` (internal) and `GET /profiles/{id}/computed_stats`.
- **Sync:** `POST /sync/up` and `GET /sync/down` with cursor-based pagination.

The sample FastAPI application in [`cloud/api/main.py`](../cloud/api/main.py) wires these endpoints to in-memory stores and demonstrates NDJSON handling, conflict resolution, and tenant scoping.

## Pricing Tiers & Privacy

- **Local (free):** 100% offline, manual backups.
- **Standard:** Cloud backups, curated library updates, monthly computed stats refresh.
- **Pro:** Benchmarking, optimization recommendations, anomaly detection, 30-day telemetry retention.
- **Enterprise:** SSO, custom models, SLAs, on-prem mirrors.

Tenants opt into data contribution for pooled stats; aggregation anonymizes individual runs. Credits or discounts reward contributors.

## Implementation Phases

1. **Phase 1:** Edge-first (SQLite schema, resolver service, sync worker, optional local aggregations).
2. **Phase 2:** Cloud core (Postgres/Timescale, Auth, `/resolve`, `/sync` APIs, stats job runner).
3. **Phase 3:** Monetization features (curated library pipeline, dashboards, recommendations).
4. **Phase 4:** Marketplace for programs/recipes and multi-site fleet management.

This blueprint keeps the Home Assistant integration fully functional offline while unlocking a high-value cloud service that supports benchmarking, optimization, and long-term storage.
