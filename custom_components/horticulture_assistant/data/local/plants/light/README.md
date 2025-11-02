# Light Targets by Growth Stage

Each JSON file in this folder describes light expectations for a species across growth stages. These values inform DLI/VPD dashboards and help advisory logic detect when a plant is under- or over-exposed.

## Schema

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

### Field Notes

- `ppfd_umol_m2_s` – Instantaneous photon flux density ranges.
- `dli_mol_m2_day` – Daily light integral bands; coordinators compare actual DLI to this range.
- `photoperiod_hours` – Optional; specify light/dark cycles if plants require strict photoperiods.
- `spectrum` – Preferred spectral mix or correlated color temperature.

## Adding New Species

1. Name the file using the species slug (e.g., `persea_americana.json`).
2. Populate stages relevant to the crop (`propagation`, `vegetative`, `flowering`, etc.).
3. Include notes for acclimation, shading tolerance, or any cultivar-specific nuances.
4. Add at least one citation in `sources`.

Remember to run `pre-commit run --all-files` after editing to keep formatting consistent.
