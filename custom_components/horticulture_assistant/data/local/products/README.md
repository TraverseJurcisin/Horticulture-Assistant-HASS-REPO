# Local Product Overrides

Use this folder for site-specific catalogues that should not be shared publicly. Files placed here are merged with the global fertilizer dataset at runtime but are skipped by CI validation.

Typical examples:

- Proprietary nutrient blends or stock solutions made on-site.
- Restricted-use pesticides for which you hold local licensing.
- Beneficial microbe brews, compost teas, or hormone mixes with farm-specific recipes.

## File Format

The JSON structure mirrors the main fertilizer schema but can omit fields that are irrelevant for your operation. Suggested minimal payload:

```json
{
  "product": {
    "product_id": "LOCAL-A123",
    "name": "Farm Blend 8-3-10",
    "manufacturer": "MyGreenhouse"
  },
  "analysis": {
    "guaranteed": {
      "N": 8,
      "P2O5": 3,
      "K2O": 10
    }
  },
  "application": {
    "methods": ["fertigation"],
    "recommended_dilution": "1:150"
  },
  "notes": {
    "sources": ["In-house formulation 2025"]
  }
}
```

## Tips

- Prefix IDs with `LOCAL-` (or similar) to avoid collisions with upstream dataset IDs.
- Because CI does not validate these files, double-check units and formatting manually.
- If you need to keep recipes entirely private, add the folder to your local backups but keep `.gitignore` entries consistent with your security requirements.

This directory is the best place to stash any operational knowledge that is unique to your facility.
