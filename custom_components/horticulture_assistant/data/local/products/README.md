# Local Product Overrides

Use this folder for proprietary or site-specific product catalogues. Files
placed here are merged with the global fertilizer dataset at runtime but are
never validated by CI, making it safe to store restricted-use formulations or
internal recipes.

---

## File Format

Local records follow the same shape as the global fertilizer schema but can omit
fields that are irrelevant to your workflow.

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
    "sources": ["In-house formulation 2025"],
    "restricted_use": true
  }
}
```

### Tips

- Prefix IDs with a site-specific namespace (e.g., `LOCAL-`, `FARM-`) to avoid
  collisions with upstream catalogues.
- Include enough metadata for advisors and analytics to produce meaningful
  recommendations (application methods, dilution rates, hazard notes).
- Because CI skips these files, manually review units and ranges before deploying
  automation based on them.
- Consider encrypting or excluding the folder from backups if it contains
  proprietary recipes.

Local overrides are optional—delete files to fall back to the shared catalogue.
