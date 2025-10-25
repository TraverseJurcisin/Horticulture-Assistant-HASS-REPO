# Data Validation Reference

Horticulture Assistant ships JSON Schema definitions for all profile and event payloads.
The schemas live under [`custom_components/horticulture_assistant/data/schema/`](../custom_components/horticulture_assistant/data/schema/)
and are consumed at runtime when profiles or history events are recorded.

## Profiles

* Schema: [`bio_profile.schema.json`](../custom_components/horticulture_assistant/data/schema/bio_profile.schema.json)
* Enforcement: Profiles added through the options flow or imported from disk are
automatically validated. Any violations trigger a persistent notification in Home Assistant
listing the affected profile IDs alongside the schema error so configuration mistakes can be
corrected quickly. The notification clears on the next reload once the JSON issues are fixed.
Home Assistant's issue registry also receives an entry for every invalid profile. The issue ID
matches `invalid_profile_<profile_id>` so supervisors can subscribe to updates or surface the
problem in dashboards. Once the JSON is corrected and the integration reloaded, the issue is
automatically dismissed.

* Threshold ranges: Manual overrides entered via the configuration flow are checked against
  agronomic guard rails before the profile is saved. Temperature, humidity, moisture, EC, CO₂,
  VPD, and illuminance thresholds must stay within the supported ranges and minimum values
  cannot exceed their corresponding maximums. If a value is out of bounds the form highlights the
  offending fields and surfaces a base error explaining the mismatch. The same validations run
  whenever profiles are reloaded from disk, so mistakes made in a text editor still raise a Repairs
  issue and block the configuration until corrected.

## Event Payloads

All event services (`record_run_event`, `record_harvest_event`, `record_nutrient_event`,
and `record_cultivation_event`) now validate their payloads before persisting history.
Invalid requests are rejected with a `ValueError` that propagates to Home Assistant
as a user-friendly `HomeAssistantError`.

Key constraints include:

* `yield_grams`, `area_m2`, and other harvest weights must be zero or positive.
* Nutrient solution measurements cannot be negative and pH must fall between 0 and 14.
* Run statistics such as `success_rate` are clamped to the `[0, 1]` range.
* All timestamps must be ISO-8601 strings with timezone offsets (UTC is assumed when omitted).
* Metadata blocks must be JSON objects, while tags and additives must be sequences of strings.
* Required identifiers (`event_id`, `run_id`, `profile_id`) require at least one character.

Example failure response from the `record_nutrient_event` service:

```
HomeAssistantError: nutrient event validation failed: ph: must be ≤ 14.0; applied_at: expected an ISO-8601 timestamp
```

Consult the schema files for a full list of constraints. Contributors can also invoke
`python -m jsonschema --instance <payload.json> --schema bio_profile.schema.json` during
development to lint bespoke payloads before submitting changes.

## Reference dataset watchdog

Critical catalogues such as fertilizer inventories, crop targets, irrigation schedules,
and deficiency lookups are checked in the background every few hours. If a bundled dataset
or local override fails to load (for example due to invalid JSON), Home Assistant raises a
persistent notification and opens a Repairs issue identifying the file that needs attention.
Fix the file or remove the override and the integration automatically dismisses the alert and
closes the Repairs issue on the next health check.

## Sensor linking hints

The configuration and options flows analyse the current Home Assistant state registry to
suggest likely sensor matches. Device class, unit of measurement, and entity naming heuristics
drive the ranking so legitimate moisture, EC, CO₂, and temperature readings bubble to the top
of each dropdown. Suggestions are optional—entering a custom entity ID still works—but the
pre-filled list eliminates guesswork for most setups and helps new growers connect the right
telemetry on the first try.
