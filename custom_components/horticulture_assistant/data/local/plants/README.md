# Plant Template Overview

Templates under `plants/` capture stage-based guidance that seeds new profiles.
They can be cloned via the options flow or referenced by services to materialise
thresholds.

```
plants/
├── README.md
├── light/
│   └── README.md
├── temperature/
│   └── README.md
└── … (add humidity, nutrients, etc. as needed)
```

---

## How Templates Are Used

- The options flow **Clone thresholds** step reads these files to populate
  overrides when you create a new profile.
- `ProfileRegistry` merges template values when a line/cultivar omits a field.
- Coordinators compare live telemetry against these targets to compute advisory
  statuses (e.g., DLI gaps, heat stress warnings).

Each template file should include:

- A `species` slug (matching the profile lineage).
- Stage keys (`propagation`, `vegetative`, `flowering`, etc.).
- Structured ranges or targets with units embedded in the field names.
- Optional `sources` metadata citing the research or experience that informed
  the targets.

---

## Contribution Tips

1. Keep schemas consistent across species so tooling can diff and validate
   changes.
2. Provide ranges instead of single values when possible; use `[min, max]`
   arrays for clarity.
3. Document any new categories you introduce by adding a README to the folder
   and referencing it here.
4. Run `pre-commit run --all-files` after editing to ensure formatting stays
   consistent.

See the subdirectories for field-level specifics:

- [Light targets](light/README.md)
- [Temperature targets](temperature/README.md)
