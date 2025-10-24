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

## Event Payloads

All event services (`record_run_event`, `record_harvest_event`, `record_nutrient_event`,
and `record_cultivation_event`) now validate their payloads before persisting history.
Invalid requests are rejected with a `ValueError` that propagates to Home Assistant
as a user-friendly `HomeAssistantError`.

Key constraints include:

* `yield_grams`, `area_m2`, and other harvest weights must be zero or positive.
* Nutrient solution measurements cannot be negative and pH must fall between 0 and 14.
* Run statistics such as `success_rate` are clamped to the `[0, 1]` range.
* Required identifiers (`event_id`, `run_id`, `profile_id`) require at least one character.

Example failure response from the `record_nutrient_event` service:

```
HomeAssistantError: nutrient event validation failed: ph: 15.2 is greater than the maximum of 14
```

Consult the schema files for a full list of constraints. Contributors can also invoke
`python -m jsonschema --instance <payload.json> --schema bio_profile.schema.json` during
development to lint bespoke payloads before submitting changes.

## Reference dataset watchdog

Critical catalogues such as fertilizer inventories, crop targets, irrigation schedules,
and deficiency lookups are checked in the background every few hours. If a bundled dataset
or local override fails to load (for example due to invalid JSON), Home Assistant raises a
persistent notification identifying the file that needs attention. Fix the file or remove the
override and the integration automatically dismisses the alert on the next health check.

## Sensor linking hints

The configuration and options flows analyse the current Home Assistant state registry to
suggest likely sensor matches. Device class, unit of measurement, and entity naming heuristics
drive the ranking so legitimate moisture, EC, CO₂, and temperature readings bubble to the top
of each dropdown. Suggestions are optional—entering a custom entity ID still works—but the
pre-filled list eliminates guesswork for most setups and helps new growers connect the right
telemetry on the first try.
