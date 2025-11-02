# Light Targets by Growth Stage

Each JSON file defines photon/light expectations for a species across growth
stages. Coordinators use these values to compute DLI gaps and surface advisory
messages when plants drift from target ranges.

---

## Schema Overview

```json
{
  "species": "solanum_lycopersicum",
  "stages": {
    "propagation": {
      "ppfd_umol_m2_s": [150, 250],
      "dli_mol_m2_day": [8, 12],
      "photoperiod_hours": [16, 18],
      "spectrum": "full-spectrum, 5000K"
    },
    "vegetative": {
      "ppfd_umol_m2_s": [300, 450],
      "dli_mol_m2_day": [18, 24],
      "notes": "Increase blue fraction for compact growth"
    }
  },
  "sources": ["Extension bulletin XYZ", "Grower case study 2024"]
}
```

Fields:

- `ppfd_umol_m2_s` – Instantaneous photon flux density range (µmol·m⁻²·s⁻¹).
- `dli_mol_m2_day` – Daily light integral band (mol·m⁻²·day⁻¹) used by the DLI
  calculator.
- `photoperiod_hours` – Optional light/dark cycle for photoperiod-sensitive
  species.
- `spectrum` – Preferred spectral mix or CCT notes.
- `notes` – Freeform adjustments, shading recommendations, acclimation tips.
- `sources` – Citations or experience notes.

---

## Adding New Species

1. Name the file using the species slug (e.g., `persea_americana.json`).
2. Populate every relevant stage; coordinators gracefully ignore missing stages
   but consistent coverage improves advisory accuracy.
3. Include at least one citation in `sources` for traceability.
4. Run `pre-commit run --all-files` to normalise JSON formatting.

If you introduce new fields, document them here and update any tooling that
consumes light templates (`profile_registry`, analytics pipelines, services).
