# Local Working Data

The `local/` directory is created under your Home Assistant config path (`config/custom_components/horticulture_assistant/data/local/`). Everything here is user-specific and safe to edit or backup.

## Contents

| File/Folder | Purpose |
|-------------|---------|
| `profiles/` | JSON documents created through the Options flow or by hand. Each file contains sensors, thresholds, and profile metadata. |
| `products/` | Private catalogues for fertilizers, pesticides, growth media, or microbial inoculants that should stay local. |
| `plants/` | Reference templates (light/temperature) used when cloning or generating profiles. |
| `zones.json` | Registry that maps irrigation/lighting/ventilation zones to profiles; consumed by automation hooks. |
| `cache/` (runtime) | Temporary exports, analytics snapshots, and AI prompts. Created on demand. |

## Profile JSON Primer

Each profile file (e.g., `avocado.json`) contains:

```json
{
  "name": "Avocado",
  "sensors": {
    "temperature": "sensor.greenhouse_temp",
    "humidity": "sensor.greenhouse_rh"
  },
  "thresholds": {
    "vpd_min": 0.6,
    "vpd_max": 1.2
  },
  "notes": "Add foliar calcium during fruit set"
}
```

You can edit these files while Home Assistant is running; the integration will reload on the next coordinator refresh.

## Best Practices

- Keep this directory under version control if you want portable greenhouse configurations.
- Sensitive/large datasets (e.g., commercial formulations) belong here rather than in the shared `data/` catalogue.
- After manual edits, run `pre-commit run --all-files` to ensure formatting stays consistent.

See the sub-Readmes for more detail:

- [Plant templates](plants/README.md)
- [Light targets](plants/light/README.md)
- [Temperature targets](plants/temperature/README.md)
- [Local products](products/README.md)
