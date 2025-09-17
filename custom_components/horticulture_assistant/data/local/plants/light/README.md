# Light guidelines

Files in this folder describe how much light a crop wants during each growth stage. Typical keys include:

- `ppfd_umol_m2_s` – Instantaneous photosynthetic photon flux density targets.
- `dli_mol_m2_day` – Daily light integral band (min/target/max).
- `spectrum` – Desired spectral mix or correlated color temperature.
- `photoperiod_hours` – Light/dark schedule recommendations.
- `annotations` – Notes on light response, shading sensitivity, or acclimation advice.

Each JSON document is named after the crop/species slug (e.g. `solanum_lycopersicum.json`). Stage definitions mirror those used throughout the integration (`propagation`, `vegetative`, `flowering`, `fruiting`, etc.).

When contributing data:
1. Keep units explicit.
2. Include citations or source notes in the `annotations` section.
3. Validate with `python -m scripts.validate_profiles` before committing.
