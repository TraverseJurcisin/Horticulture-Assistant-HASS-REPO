# History Export Reference

The history exporter mirrors every lifecycle event recorded through the Home Assistant services to append-only JSON Lines files. These live alongside the existing profile data in your Home Assistant configuration directory, providing an easy way to analyse crop performance outside of Home Assistant.

## Directory layout

All files are created under:

```
config/custom_components/horticulture_assistant/data/local/history/
```

For each profile (`<profile_id>`) the exporter keeps the following structure:

```
<profile_id>/
  run_events.jsonl
  harvest_events.jsonl
  nutrient_events.jsonl
  cultivation_events.jsonl
index.json
```

Each line in the `*.jsonl` files is a standalone JSON object describing a single event exactly as it was validated and stored by the profile registry. Lines are written atomically so you can safely tail the files from external processes.

## Sample entries

### Harvest event

```
{"applied_at": null, "harvest_id": "harvest-1", "harvested_at": "2025-02-10T00:00:00+00:00", "profile_id": "p1", "run_id": null, "species_id": null, "yield_grams": 42.0}
```

### Nutrient event

```
{"event_id": "nutrient-15", "profile_id": "p1", "applied_at": "2025-02-11T07:30:00+00:00", "product_id": "CalMag-A", "solution_volume_liters": 45.0, "metadata": {"mix_batch": "tank-17"}}
```

### Cultivation event

```
{"event_id": "inspect-9", "profile_id": "p1", "recorded_at": "2025-02-09T18:00:00+00:00", "event_type": "inspection", "notes": "Checked for aphids", "severity": "routine"}
```

## Index manifest

The exporter keeps a global `index.json` in the root of the history directory. The manifest is a map keyed by profile id with event counters and the ISO timestamp of the most recent update:

```
{
  "p1": {
    "profile_id": "p1",
    "last_updated": "2025-02-11T07:30:00+00:00",
    "counts": {
      "harvest": 4,
      "nutrient": 9,
      "cultivation": 12
    }
  }
}
```

The index file is rewritten atomically via a temporary file so other processes can read it without worrying about partial updates.

## Consuming the logs

Because the exporter uses JSON Lines you can bring the data into analytics tools with a single command:

```bash
python -m pandas json_normalize $(cat config/custom_components/horticulture_assistant/data/local/history/p1/harvest_events.jsonl)
```

For more advanced pipelines you can watch the directory and stream new lines into a time-series database or cloud dashboard. The index manifest makes it trivial to track which profiles have fresh data when orchestrating nightly sync jobs.

### Rolling analytics snapshots

Every time a lifecycle event is recorded the registry recomputes lightweight analytics snapshots. The `yield/v1` payload now
includes:

- `window_totals` with 7/30/90 day buckets summarising harvest counts, total yield, fruit counts, and the last timestamp.
- `days_since_last_harvest` so automations can respond to stale production without deriving their own timers.
- `total_fruit_count` metrics that mirror the cumulative gram totals, both overall and within each rolling window.

Nutrient and cultivation statistics already exposed `window_counts`; the additional harvest metrics make it easy to build
weekly dashboards or export recent momentum directly from diagnostics without replaying the JSONL feeds.

### Command-line exports

If you prefer to convert the JSONL feeds into CSV or prettified JSON, the bundled profile manager script now exposes an `export-history` command:

```bash
python scripts/profile_manager.py export-history basil run_events -o out/run_events.csv --format csv --limit 250
```

Supported formats are `jsonl` (default), `json`, and `csv`. Passing `--limit` exports only the most recent entries, which helps when building rolling reports without copying the entire log each time.

## Retention and backups

The exporter never deletes entries; prune the files manually if you prefer rolling windows. Since everything lives under `data/local/`, you can back up the folder alongside your profile JSON files to preserve full historical context when migrating installations.
