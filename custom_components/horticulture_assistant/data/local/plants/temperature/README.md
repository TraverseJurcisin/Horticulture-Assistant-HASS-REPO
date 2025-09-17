# Temperature guidelines

Stage-aware temperature bands live here. Each JSON file follows the pattern:

```json
{
  "species": "persea_americana",
  "stages": {
    "propagation": {
      "air_day_c": [24, 26],
      "air_night_c": [18, 20],
      "root_zone_c": [22, 24],
      "notes": "Bottom heat speeds rooting by ~20%"
    },
    "vegetative": { "air_day_c": [21, 24], ... }
  }
}
```

Include separate ranges for day/night when relevant, plus optional `humidity_target`, `ventilation_trigger`, or `frost_warning` keys if the crop demands them.

Add citations in a `sources` array so we can audit agronomic recommendations. As always, validate with `python -m scripts.validate_profiles` before committing.