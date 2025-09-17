# Fertilizer, substrate, and additive index

This dataset powers product lookups for fertilizers, growth media, biostimulants, and crop-protection inputs. It is split into lightweight index shards for fast search and richer detail records for downstream analytics.

```
fertilizers/
+-- fertilizer_application_methods.json     # Standard practice lookups (broadcast, fertigate, foliar, etc.)
+-- fertilizer_application_rates.json       # Reference dose ranges per crop class
+-- index_sharded/                          # JSONL search shards (~5k records each)
+-- detail/                                 # Full product dossiers grouped by leading ID bytes
+-- schema/2025-09-V3e.schema.json           # Canonical JSON Schema for detail records
```

## Record structure (detail JSON)
Each detail file stores exactly one product record with the following high-level keys:

| Key | Description |
|-----|-------------|
| `id` | Deterministic 6-character identifier (hex) used across index/detail datasets. |
| `name`, `brand`, `manufacturer` | Human-readable product metadata. |
| `analysis` | Guaranteed, derived, and minimum nutrient percentages (NPK + micros). |
| `formulation` | Product form (liquid, granular, soluble), carrier, density, pH, EC, solubility. |
| `application` | Supported methods, dilution ratios, compatible injection systems, re-entry intervals. |
| `regulatory` | Organic status, OMRI/WSDA equivalence, restricted-use flags, heavy metal compliance. |
| `safety` | PPE requirements, hazard statements, storage notes. |
| `notes.sources` | Bibliography or dataset provenance entries. |

Refer to the schema file for the complete nested structure, data types, and optional fields.

## Editing workflow
1. Pick an ID for the new product (preferably the next available hexadecimal shard).
2. Add the full record under `detail/XY/XYZ123.json` where `XY` are the first two characters of the ID.
3. Append a summary row to the appropriate shard in `index_sharded/` with the minimal search payload:
   ```json
   {
     "id": "XYZ123",
     "name": "Example 8-3-9",
     "type": "fertilizer",
     "guaranteed_nutrients": {"N": 8, "P2O5": 3, "K2O": 9},
     "tags": ["veg", "organic"],
     "source": "Manufacturer bulletin 2024"
   }
   ```
4. Run the migration helpers if you changed the schema: `python scripts/migrate_fertilizer_schema.py`.
5. Validate with `python -m scripts.validate_profiles` and commit.

## Provenance & quality
- Original records were blended from state fertilizer registries and vendor SDS/labels.
- Newer entries add greenhouse/media performance data contributed by growers and agronomists.
- Heavy metal screens follow state banding rules; see `heavy_metals` within each record for thresholds.

Keep contributions well-sourced so the audit trail remains trustworthy.
