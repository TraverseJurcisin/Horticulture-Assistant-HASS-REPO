# Plant Template Overview

The `plants/` directory holds template data that can be cloned into new profiles. Each file captures stage-based guidance gathered from agronomy references.

```
plants/
├── README.md
├── light/
│   └── README.md
├── temperature/
│   └── README.md
└── ... (future folders: humidity, nutrient baselines, etc.)
```

## Usage

- Options flow “Clone thresholds from” pulls defaults from these templates.
- Coordinators reference the data when generating advisory metrics (e.g., comparing actual DLI to target DLI).
- You can add additional categories (humidity, CO₂, etc.) by creating matching folders and documenting them here.

## Contribution Guidelines

1. Keep units explicit (e.g., `dli_target_mol_m2_day`).
2. Provide `sources` arrays whenever data is derived from research or extension bulletins.
3. Avoid including per-location microclimate data—store that in `data/local/` instead.

See the subdirectories for detailed formats:

- [Light targets](light/README.md)
- [Temperature targets](temperature/README.md)
