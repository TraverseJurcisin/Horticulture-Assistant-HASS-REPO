# Local plant knowledge

The files in this folder capture curated reference material that ships with the integration and can be extended by end users. They are distinct from the per-profile records stored in the `profiles/` folder—think of them as templates, reference tables, and guardrails.

Current categories:
- `light/` – Stage-based PPFD, DLI, photoperiod, and spectrum recommendations for supported crops.
- `temperature/` – Baseline targets for day/night air temperature, substrate temperature, and root-zone differentials.

Add your own folders if you have localized guidance (e.g. humidity bands, CO2 ramps); the integration will happily read additional JSON as long as you follow the schemas used in other datasets.