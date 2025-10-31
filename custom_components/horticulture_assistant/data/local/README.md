# Local Working Data

`data/local/` is created under your Home Assistant configuration directory
(`config/custom_components/horticulture_assistant/data/local/`). Everything here
is site-specific and safe to edit, back up, or version-control.

---

## Contents

| Path | Purpose |
|------|---------|
| `profiles/` | JSON documents managed by the Profile Registry. Each file represents a line/zone and stores overrides, sensor bindings, and metadata. |
| `plants/` | Template datasets (light, temperature, etc.) that seed new profiles through the options flow. |
| `products/` | Private fertilizer/pesticide catalogues merged with the global dataset at runtime but skipped by CI. |
| `zones.json` | Mapping between irrigation/lighting/ventilation zones and profile IDs for automation helpers. |
| `cache/` *(created on demand)* | Export snapshots, AI prompts/responses, and derived analytics cached by services. |
| `history/` *(optional)* | When enabled, lifecycle logging services can mirror JSONL history here for external processing. |

Folders are generated automatically the first time the integration runs. Missing
folders are recreated on reload.

---

## Editing Profiles

Profiles are standard JSON files. The registry reloads them automatically when
the file changes, so you can iterate quickly:

```jsonc
{
  "id": "alicante_tomato_north_bed",
  "display_name": "Alicante Tomato – North Bed",
  "species": "solanum_lycopersicum",
  "cultivar": "alicante",
  "sensors": {
    "temperature": "sensor.greenhouse_temp",
    "humidity": "sensor.greenhouse_rh"
  },
  "overrides": {
    "environment": {
      "temperature": {
        "min_c": 19.5,
        "max_c": 28.0
      }
    }
  }
}
```

Tips:

- Remove a key to fall back to cultivar/species defaults.
- Use the options flow **Clone thresholds** action to materialise inherited
  values before editing.
- Run `python scripts/validate_profiles.py` to check for structural issues before
  reloading Home Assistant.

---

## Best Practices

- Keep this directory under version control (or at minimum in your backups) to
  preserve configuration history.
- Place proprietary or site-specific datasets in `products/` rather than the
  shared catalogue.
- Document any new template categories you add under `plants/` with a README so
  future contributors understand the schema.
- Sensitive data (API keys, private research) should remain outside the
  repository—adjust `.gitignore` in your Home Assistant config if necessary.

See the nested READMEs for template specifics:

- [Plant templates](plants/README.md)
- [Light targets](plants/light/README.md)
- [Temperature targets](plants/temperature/README.md)
- [Local products](products/README.md)
