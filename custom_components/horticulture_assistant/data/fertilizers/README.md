# Fertilizer Dataset

This dataset powers product lookups and nutrient analytics. It mirrors real-world fertilizer registries while allowing local additions for proprietary products.

## Directory Overview

```
fertilizers/
├── detail/           # One JSON per product (sharded by prefix)
├── index_sharded/    # Search-friendly JSONL shards summarizing each product
├── schema/           # JSON Schema versions (current: 2025-09-V3e)
├── fertilizer_application_methods.json
├── fertilizer_application_rates.json
└── README.md
```

- **detail/** – Rich product dossiers including guaranteed analysis, carrier, density, heavy-metal compliance, application notes, and citations.
- **index_sharded/** – Lightweight JSON Lines files used for fuzzy search; each row contains product id, name, nutrient summary, tags, and provenance.
- **schema/** – Formal schemas; V3e is validated in CI via `scripts/validate_fertilizers_v3e.py`.
- **application_*.json** – Lookup tables for application methods, rates, and best practices.

## Product Record Schema (V3e)

Key sections inside each detail JSON:

| Field | Description |
|-------|-------------|
| `product.product_id` | Deterministic hex identifier used across detail and index shards. |
| `analysis.guaranteed` | NPK + secondary/micronutrient guarantees (percent by weight). |
| `formulation` | Physical form, carrier, density, pH, EC, solubility info. |
| `application` | Supported methods (broadcast, fertigation, foliar), dilution ratios, pre-harvest intervals. |
| `regulatory` | Organic status, heavy metal test results, restricted-use notes. |
| `safety` | PPE requirements, hazard statements, storage guidance. |
| `notes.sources` | Citations or dataset sources for auditability. |

Refer to the schema file for precise data types and optional fields.

## Workflow for Adding Products

1. Choose an ID (e.g., `A1B2C3`) and place the detail file under `detail/A1/A1B2C3.json`.
2. Populate the record using the V3e schema.
3. Append a minimal row to the appropriate JSONL shard in `index_sharded/` to keep CLI search fast.
4. Run `python scripts/validate_fertilizers_v3e.py` and ensure no errors are reported.
5. Document sources in the `notes.sources` array.

## Quality Assurance

- CI runs the V3e validator on every pull request.
- Pre-commit enforces JSON formatting (`pretty-format-json`) and newline discipline.
- Large dataset updates should include a changelog in your PR description for reviewers.

If you need to keep private products local, store them under `data/local/products/` instead—those files are merged at runtime but skipped by CI.
