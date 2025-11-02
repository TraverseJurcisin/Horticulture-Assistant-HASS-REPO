# Data Catalogue

The `data/` tree ships the agronomy datasets that back profile defaults,
validation, and analytics. Everything is human-readable JSON so you can audit,
extend, or replace the individual catalogues.

---

## Directory Layout

```
data/
├── dataset_catalog.json   # Machine-readable index of bundled datasets
├── fertilizers/           # Product catalogue, schema, and search shards
├── global_profiles/       # Canonical species/cultivar blueprints
├── local/                 # Site-specific overrides created at runtime
├── schema/                # Shared JSON schema fragments
├── [environment|light|temperature|...]  # Thematic reference tables
└── README.md
```

Highlights:

- [Fertilizers](fertilizers/README.md) – Detail shards, search indexes, and the
  V3e schema used to validate nutrient products.
- [Local working data](local/README.md) – Profiles, plant templates, and private
  catalogues that live alongside a Home Assistant install.
- [Plant templates](local/plants/README.md) – Stage-based light/temperature
  targets that populate new profiles.
- Thematic folders (`environment/`, `irrigation/`, `pests/`, `yield/`, etc.)
  provide curated baselines for coordinators and advisory logic.

Every folder you extend should document its schema in a `README.md` and, when
possible, include a matching JSON schema under `schema/`.

---

## Editing Guidelines

1. **Encoding** – Use UTF-8 with a trailing newline; `pre-commit` enforces this
   automatically.
2. **Naming** – Prefer lowercase snake_case filenames (e.g.,
   `nutrient_guidelines.json`).
3. **Schemas** – Version schema files and store them next to the datasets. When
   fields change, bump the schema version and update validators.
4. **Validation** – Run `pre-commit run --all-files` and the relevant scripts in
   [`scripts/`](../../scripts/) (for example,
   `python scripts/validate_fertilizers_v3e.py`).

---

## Contributing New Datasets

- Choose the closest thematic folder or create a new one with a README that
  explains the fields and units.
- Provide `sources` arrays or metadata blocks that credit origin data.
- Keep measurements explicit (units in field names or companion metadata).
- Large/proprietary datasets can be referenced in `dataset_catalog.json` with a
  pointer to private storage; surface only the schema and sample rows publicly.

See [`docs/data_validation.md`](../../docs/data_validation.md) for more details
about repository-wide validation expectations.
