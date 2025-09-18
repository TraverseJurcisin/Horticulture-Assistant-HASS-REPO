# Data catalogue

This directory packages the horticulture knowledge base that powers the integration. Each subfolder focuses on a single theme (e.g. light, irrigation, pests, harvest logistics) so profiles can compose just the pieces they need.

Most datasets follow three principles:

1. **Human readable** – JSON/JSONL files that can be inspected and versioned in Git.
2. **Schema backed** – companion files inside `schema/` document the structure for automated validation.
3. **Stable identifiers** – every record gets a deterministic ID so profiles can reference data safely across releases.

## Key folders
- `fertilizers/` – indexed catalogue of nutrient products, carriers, analysis data, and compliance flags.
- `light/` – spectral targets, crop-specific PPFD/DLI bands, and lighting technology lookup tables.
- `temperature/`, `humidity/`, `co2/` – environment setpoints arranged by growth stage.
- `nutrients/`, `solution/`, `soil/` – macro/micronutrient ranges, stock solution recipes, and substrate properties.
- `pests/`, `diseases/`, `fungicides/`, `pesticides/` – risk profiles, scouting notes, and mitigation playbooks.
- `local/` – site-specific data created on the fly (profiles, zone registry, cache files). See the README within for details.

The remaining folders follow the same pattern—stage-specific agronomy, operational checklists, and supporting coefficients.

## Adding or updating data
1. Create or edit the JSON/JSONL file in the relevant folder.
2. Update or add a schema file if the structure changed.
3. Run the validation helpers before committing:
   ```bash
   python -m scripts.validate_profiles
   ```
4. Describe the source in the PR so changes remain auditable.

## Versioning
Dataset versions are encoded in filenames (e.g. `2025-09-V3e.schema.json`). When bumping versions, include a changelog line in the PR body and keep earlier revisions for reproducibility unless data privacy requires removal.
