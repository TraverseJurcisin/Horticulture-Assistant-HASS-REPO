# Local product overrides

Use this directory to stash private catalogues—products that should not live in the shared dataset or that differ for your site. Typical examples:

- House-made nutrient stock blends.
- On-farm compost teas or biological brews.
- Restricted-use pesticides that your operation is licensed to apply.

File format is identical to the global fertilizer/product schema. Drop JSON files here with unique IDs (e.g. prefix private IDs with `L` to avoid collisions). The integration merges these with the main catalogue at runtime, preferring local entries when IDs clash.

Remember to back up this folder; nothing here ships with the component.
