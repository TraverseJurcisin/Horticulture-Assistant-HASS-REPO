# Local data

This folder is created inside the Home Assistant configuration directory and stores everything that belongs to *your* installation:

- `profiles/` – Serialized plant profiles that you create through the config flow.
- `plants/` – Canonical crop knowledge pulled in for quick reference (see README inside).
- `products/` – Locally curated product overrides or private catalogues.
- `zones.json` – The zone registry that maps irrigation/lighting/ventilation zones to profiles.
- `cache/` (created at runtime) – Temporary exports, analytics snapshots, AI prompts, etc.

The integration never writes outside of this tree. Sync it with Git or your backup solution to move a greenhouse between Home Assistant instances.

### Tips
- Use `profiles/*.json` to share templates with friends or other sites.
- `zones.json` is safe to edit manually, but run `python -m scripts.validate_profiles` afterwards.
- Anything under `local/` is ignored by upgrades, so your data survives component updates.
