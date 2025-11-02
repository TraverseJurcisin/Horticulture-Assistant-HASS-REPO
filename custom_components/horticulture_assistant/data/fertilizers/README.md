# Fertilizer Dataset

This catalogue powers nutrient lookups, analytics, and advisory services. It
mirrors real-world fertilizer registries while allowing local additions under
`data/local/products/`.

---

## Directory Layout

```
fertilizers/
├── detail/                # One JSON per product (sharded by prefix)
├── index_sharded/         # JSONL shards for fast search/autocomplete
├── schema/                # JSON Schemas (current: 2025-09-V3e)
├── fertilizer_application_methods.json
├── fertilizer_application_rates.json
└── README.md
```

- **detail/** – Rich product dossiers including analysis, formulation, safety,
  application instructions, and citations.
- **index_sharded/** – Lightweight rows used by CLI tooling and options-flow
  selectors.
- **schema/** – Versioned schemas for validators and migration scripts.
- **application_*.json** – Lookup tables for UI selectors and advisory helpers.

---

## Product Record Schema (V3e)

Key sections inside each detail file:

| Field | Description |
|-------|-------------|
| `product.product_id` | Deterministic identifier referenced across detail and index shards. |
| `analysis.guaranteed` | Guaranteed NPK + secondary/micronutrient percentages. |
| `formulation` | Physical form, carrier, density, solubility, pH/EC ranges. |
| `application` | Supported methods, dilution guidance, PHI/REI notes. |
| `regulatory` | Organic status, certifications, restrictions. |
| `safety` | PPE requirements, storage guidance, hazard statements. |
| `notes.sources` | Citations or provenance for auditing. |

Consult `schema/2025-09-V3e.schema.json` for field-level detail.

---

## Adding or Updating Products

1. Choose a stable ID (e.g., `A1B2C3`) and place the detail file under
   `detail/A1/A1B2C3.json`.
2. Populate the record according to the V3e schema.
3. Append a summary row to the appropriate shard in `index_sharded/`.
4. Run the validator:
   ```bash
   python scripts/validate_fertilizers_v3e.py
   ```
5. Document sources and safety notes in the record.

For large ingestion work, `scripts/migrate_fertilizer_schema.py` and
`scripts/sort_manifest.py` help keep files consistent and sorted.

---

## Quality Assurance & Local Overrides

- CI executes `validate_fertilizers_v3e.py` on pull requests.
- `pre-commit` enforces JSON formatting and newline discipline.
- Use `scripts/edge_sync_agent.py` or Home Assistant services to export merged
  datasets when debugging downstream consumers.
- Store proprietary formulations under `data/local/products/`; those files are
  merged at runtime but bypass validation.

See `docs/scripts_overview.md` for more about available tooling.
