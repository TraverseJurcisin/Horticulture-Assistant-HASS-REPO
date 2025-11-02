# Data Catalogue

The `data/` tree ships with reference material that powers derived metrics, profile templates, and fertilizer validation. Everything is stored as human-readable JSON so you can audit or replace individual datasets.

## Layout

```
data/
├── fertilizers/           # Product catalogue, schema, and search indexes
├── local/                 # User-specific working data (profiles, zones, overrides)
├── ...                    # Agronomy reference tables (environment, pests, irrigation, etc.)
```

Each subdirectory has its own README with full descriptions. Highlighted areas:

- [Fertilizers](fertilizers/README.md) – sharded product listings, detail schema, and the CI validator.
- [Local working data](local/README.md) – where Home Assistant writes profiles and zone registries.
- [Plants/light](local/plants/light/README.md) – stage-based light targets for template profiles.
- [Plants/temperature](local/plants/temperature/README.md) – air/root temperature guidelines used by coordinators.
- [Products](local/products/README.md) – private catalogues for fertilizers, pesticides, or additives that should stay local.

## Editing Guidelines

1. **UTF-8 and newline** – Pre-commit enforces one trailing newline and LF line endings.
2. **Naming** – Use lowercase snake_case filenames (`nutrient_guidelines.json`).
3. **Schemas** – Schema files live alongside data (e.g., `fertilizers/schema/2025-09-V3e.schema.json`). Update schemas when fields change and bump validators.
4. **Validation** – Run `pre-commit run --all-files` and `python scripts/validate_fertilizers_v3e.py` before committing.

## Contributing New Datasets

- Drop the JSON in the appropriate subdirectory.
- Document the schema assumptions in that folder’s README.
- Provide source attribution where possible (e.g., extension bulletins, research papers).
- If the dataset is large or proprietary, consider storing only metadata here and referencing your private location in `local/`.

For details about specific themes (environment, irrigation, pests, etc.) open the corresponding README in this directory.
