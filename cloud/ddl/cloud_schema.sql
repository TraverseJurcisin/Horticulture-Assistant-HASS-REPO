-- Cloud schema for Horticulture Assistant centralized services
-- PostgreSQL + TimescaleDB compatible

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Tenancy --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
  tenant_id    uuid PRIMARY KEY,
  name         text NOT NULL,
  plan         text NOT NULL CHECK (plan IN ('free','standard','pro','enterprise')),
  created_at   timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
  user_id      uuid PRIMARY KEY,
  tenant_id    uuid REFERENCES tenants(tenant_id),
  email        citext UNIQUE NOT NULL,
  role         text NOT NULL CHECK (role IN ('admin','maintainer','operator','viewer')),
  created_at   timestamptz DEFAULT now()
);

-- Library profiles -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS bio_profiles (
  profile_id   uuid PRIMARY KEY,
  tenant_id    uuid NULL REFERENCES tenants(tenant_id) ON DELETE SET NULL,
  profile_type text NOT NULL CHECK (profile_type IN ('species','cultivar','line')),
  identity     jsonb NOT NULL,
  taxonomy     jsonb NOT NULL,
  parents      jsonb,
  policies     jsonb,
  stable_knowledge jsonb,
  lifecycle    jsonb,
  curated_targets jsonb,
  diffs_vs_parent jsonb,
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS profile_links (
  parent_id uuid REFERENCES bio_profiles(profile_id) ON DELETE CASCADE,
  child_id  uuid REFERENCES bio_profiles(profile_id) ON DELETE CASCADE,
  PRIMARY KEY (parent_id, child_id)
);

-- Computed stats -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profile_computed_stats (
  profile_id     uuid REFERENCES bio_profiles(profile_id) ON DELETE CASCADE,
  stats_version  text NOT NULL,
  computed_at    timestamptz NOT NULL,
  snapshot_id    text,
  payload        jsonb NOT NULL,
  PRIMARY KEY (profile_id, stats_version, computed_at)
);

CREATE TABLE IF NOT EXISTS profile_contributions (
  profile_id     uuid NOT NULL,
  child_id       uuid NOT NULL,
  stats_version  text NOT NULL,
  computed_at    timestamptz NOT NULL,
  n_runs         integer NOT NULL,
  weight         double precision NOT NULL,
  PRIMARY KEY (profile_id, child_id, stats_version, computed_at)
);

-- Runs and telemetry ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
  run_id         uuid PRIMARY KEY,
  tenant_id      uuid NOT NULL REFERENCES tenants(tenant_id),
  parent_profile_id uuid REFERENCES bio_profiles(profile_id),
  header         jsonb NOT NULL,
  batch_tags     text[] DEFAULT ARRAY[]::text[],
  created_at     timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS yields (
  run_id         uuid REFERENCES runs(run_id) ON DELETE CASCADE,
  ts             timestamptz NOT NULL,
  mass_kg        double precision,
  count_n        double precision,
  area_m2        double precision,
  kg_per_m2      double precision,
  grade          text,
  loss_reason    text,
  PRIMARY KEY (run_id, ts)
);

CREATE TABLE IF NOT EXISTS telemetry (
  tenant_id      uuid NOT NULL,
  run_id         uuid REFERENCES runs(run_id) ON DELETE CASCADE,
  metric         text NOT NULL,
  ts             timestamptz NOT NULL,
  value          double precision,
  source         text,
  calibrated     boolean DEFAULT false,
  PRIMARY KEY (tenant_id, run_id, metric, ts)
);
SELECT create_hypertable('telemetry', by_range('ts'), if_not_exists => TRUE, migrate_data => TRUE);

-- Sync log -------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_events (
  event_id       uuid PRIMARY KEY,
  tenant_id      uuid NOT NULL REFERENCES tenants(tenant_id),
  device_id      text NOT NULL,
  ts             timestamptz NOT NULL,
  entity_type    text NOT NULL,
  entity_id      uuid NOT NULL,
  op             text NOT NULL,
  patch          jsonb,
  vector         jsonb,
  actor          text,
  hash_prev      text
);

CREATE INDEX IF NOT EXISTS idx_sync_events_tenant_ts ON sync_events(tenant_id, ts DESC);

-- Helper views ----------------------------------------------------------------
CREATE VIEW IF NOT EXISTS run_latest_events AS
SELECT DISTINCT ON (entity_id) entity_id, event_id, ts
FROM sync_events
ORDER BY entity_id, ts DESC;

