# Temperature Targets

Temperature templates define recommended air and root-zone conditions for each
stage. Coordinators reference these values to raise binary sensors, compute heat
stress warnings, and enrich the provenance reports returned by services.

---

## Schema Overview

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

Common fields:

- `air_day_c` / `air_night_c` – Day/night air temperature ranges in °C.
- `root_zone_c` – Root-zone media temperature targets (hydroponics or heated
  benches).
- `humidity_target_percent` – Optional humidity bands that pair well with the
  listed temperatures.
- `stress_thresholds` – Boundaries that drive status sensors and automation
  triggers.
- `notes` and `sources` – Context and traceability.

---

## Contribution Tips

1. Use `[min, max]` arrays even when you only have a single value; it keeps the
   schema uniform.
2. Add new keys only when coordinators or analytics consume them—otherwise document
   optional fields here.
3. Update related tooling (`profile_registry`, `sensor_validation`, analytics)
   if you introduce new measurements.
4. Run `pre-commit run --all-files` to normalise formatting.

Temperature templates complement light templates; keep stages aligned so cloned
profiles inherit coherent targets across environment dimensions.
