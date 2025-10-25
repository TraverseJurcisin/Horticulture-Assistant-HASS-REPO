# Schema Reference

Horticulture Assistant ships JSON Schema documents for every payload stored on disk or accepted
through a Home Assistant service. This page highlights the most common objects and links directly
to the bundled schema files so contributors can cross-check their changes without digging through
the source tree.

## BioProfile envelope

Profiles are persisted as BioProfile envelopes. The schema lives at
[`custom_components/horticulture_assistant/data/schema/bio_profile.schema.json`](../custom_components/horticulture_assistant/data/schema/bio_profile.schema.json)
and enforces the core shape of the profile hierarchy.

Key requirements include:

```json
{
  "profile_id": "cultivar.cherokee_purple",
  "display_name": "Cherokee Purple",
  "profile_type": "cultivar",
  "species": "species.solanum_lycopersicum",
  "parents": ["species.solanum_lycopersicum"],
  "thresholds": {
    "temperature_min": 16.0,
    "temperature_max": 30.0,
    "humidity_min": 55.0,
    "humidity_max": 80.0,
    "conductivity_min": 1400.0,
    "conductivity_max": 2200.0
  },
  "resolved_targets": {
    "temperature_min": {
      "value": 16.0,
      "annotation": {"source_type": "manual", "method": "manual"},
      "citations": []
    }
  },
  "general": {"plant_type": "Tomato", "area_sq_m": 1.2}
}
```

* `profile_id`, `display_name`, and `profile_type` are mandatory.
* `thresholds`, `resolved_targets`, and `general` must be objects (even if empty) so automation
  layers can safely merge overrides.
* History sections (`run_history`, `harvest_history`, etc.) accept arrays of the event payloads
  documented below.

## Event payloads

The service payloads for recording cultivation activity share the same schema definitions that are
embedded in the BioProfile document. The canonical files live under
[`custom_components/horticulture_assistant/data/schema/`](../custom_components/horticulture_assistant/data/schema/).

### Harvest events — `$defs.harvest_event` in [`bio_profile.schema.json`](../custom_components/horticulture_assistant/data/schema/bio_profile.schema.json)

```json
{
  "harvest_id": "harvest-2024-08-14",
  "profile_id": "cultivar.cherokee_purple",
  "species_id": "species.solanum_lycopersicum",
  "harvested_at": "2024-08-14T07:15:00Z",
  "yield_grams": 640.0,
  "area_m2": 1.2,
  "notes": "Cluster pruning kept internodes compact."
}
```

* `harvest_id`, `profile_id`, and `harvested_at` are required.
* Weight and area are constrained to non-negative numbers.
* `harvested_at` must be an ISO-8601 timestamp (timezone is required for cross-site rollups).
* `metadata` must be a JSON object when present.

### Nutrient applications — `$defs.nutrient_event` in [`bio_profile.schema.json`](../custom_components/horticulture_assistant/data/schema/bio_profile.schema.json)

```json
{
  "event_id": "nutrient-2024-08-13",
  "profile_id": "cultivar.cherokee_purple",
  "applied_at": "2024-08-13T18:00:00Z",
  "product_id": "fertilizer.masterblend_4_18_38",
  "solution_volume_liters": 40.0,
  "concentration_ppm": 900,
  "ec_ms": 2.1,
  "ph": 6.2
}
```

* `product_id` must point at a known fertilizer entry; concentrations and pH obey non-negative and
  `[0, 14]` bounds respectively.
* `additives` must be provided as a list of strings. Supplying a set results in a validation warning
  that explains how to convert to a deterministic list.

### Cultivation events — `$defs.cultivation_event` in [`bio_profile.schema.json`](../custom_components/horticulture_assistant/data/schema/bio_profile.schema.json)

```json
{
  "event_id": "inspection-2024-08-12",
  "profile_id": "cultivar.cherokee_purple",
  "occurred_at": "2024-08-12T10:00:00Z",
  "event_type": "inspection",
  "notes": "Checked for leaf miners; none observed.",
  "metric_value": 22.5,
  "metric_unit": "°C"
}
```

* `event_type` drives analytics rollups and should match one of the documented stage activities.
* `tags` must be a list (or other ordered sequence) of strings and `metadata` must be an object.
* `occurred_at` enforces ISO-8601 timestamps to keep audit logs consistent across timezones.

### Run lifecycle snapshots — [`run_event.schema.json`](../custom_components/horticulture_assistant/data/schema/run_event.schema.json)

```json
{
  "run_id": "spring-2024",
  "profile_id": "cultivar.cherokee_purple",
  "species_id": "species.solanum_lycopersicum",
  "started_at": "2024-02-01T00:00:00Z",
  "ended_at": "2024-07-28T00:00:00Z",
  "success_rate": 0.92,
  "stress_events": 3
}
```

* Success metrics are clamped to the `[0, 1]` range.
* `environment` and `metadata` objects cannot be arrays or scalars and timestamps must include
  timezone information.

## Validation tips

Use the built-in schema files to lint payloads locally:

```bash
python -m jsonschema --instance profile.json --schema custom_components/horticulture_assistant/data/schema/bio_profile.schema.json
python -m jsonschema --instance harvest.json --schema custom_components/horticulture_assistant/data/schema/harvest_event.schema.json
```

The integration also validates payloads at runtime and raises Home Assistant Repairs issues if a
profile or dataset drifts out of spec. Fix the JSON and reload the integration to clear the alerts.
