# Temperature Targets

Temperature templates describe recommended air and root-zone conditions for each growth stage. Coordinators use these values to flag environment deviations and to calculate advisory metrics.

## Schema

```json
{
  "species": "persea_americana",
  "stages": {
    "propagation": {
      "air_day_c": [24, 26],
      "air_night_c": [18, 20],
      "root_zone_c": [22, 24],
      "humidity_target_percent": [70, 80],
      "notes": "Bottom heat accelerates rooting by ~20%"
    },
    "vegetative": {
      "air_day_c": [21, 24],
      "air_night_c": [16, 18]
    }
  },
  "stress_thresholds": {
    "cold_damage_c": 4,
    "heat_stress_c": 34
  },
  "sources": ["Avocado Production Manual 2023"]
}
```

### Field Notes

- `air_day_c` / `air_night_c` – Day/night air temperature ranges.
- `root_zone_c` – Root-zone media temperature targets (useful for hydroponics or bottom-heated benches).
- `humidity_target_percent` – Optional humidity guidance paired with temperature.
- `stress_thresholds` – Boundaries above/below which stress automation can trigger.

## Contribution Tips

- Provide ranges whenever possible; single values can be represented as `[value, value]` for consistency.
- Include regional caveats in `notes` if thresholds depend on cultivar or production system.
- When integrating new fields, update any logic that consumes these templates (profile generation, dashboards).

Run `pre-commit run --all-files` after changes to ensure formatting matches repository standards.
