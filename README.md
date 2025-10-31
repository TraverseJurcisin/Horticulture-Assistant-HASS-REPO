# Horticulture Assistant for Home Assistant

**Feel like a pro grower without living in spreadsheets.** Horticulture Assistant turns Home Assistant into a greenhouse co-pilot that watches your environment, suggests the next best task, and celebrates every harvest with you.

> “It’s like having a head grower on call.” – early beta tester

---

## Why growers fall in love with it

- **It keeps the rhythm.** Friendly reminders and optional automations pace irrigation, fertilizing, and harvest prep so nothing slips through the cracks.
- **It looks gorgeous.** Light, climate, and nutrient history land in colorful dashboards that show what’s thriving at a glance.
- **It flexes with your space.** Start from curated crop templates, then fine-tune thresholds or bolt on new sensors as your setup evolves.
- **It respects your privacy.** Everything runs locally by default; optional AI helpers only wake up when you invite them.

---

## Try it this weekend (takes about 5 minutes)

### HACS (recommended)
1. In HACS, add this repo as a [Custom Repository](https://hacs.xyz/docs/faq/custom_repositories/) (Integration).
2. Search for **Horticulture Assistant**, install, and restart Home Assistant.
3. Updates arrive right inside HACS whenever we ship them.

### Manual copy
1. Copy `custom_components/horticulture_assistant/` into `config/custom_components/`.
2. Restart Home Assistant.

> Requires Home Assistant 2025.9.0 or later (see `hacs.json`).

---

## What you’ll see after install

1. Head to **Settings → Devices & Services → Add Integration** and pick **Horticulture Assistant**.
2. Complete the guided setup—no spreadsheets, API keys, or cloud accounts required.
3. Add a plant profile or link sensors from **Configure → Options** to unlock tailored insights.
4. Visit the generated device to watch climate, light, nutrient, and workflow entities come alive.

Curious what else is under the hood? The [component guide](custom_components/horticulture_assistant/README.md) walks through every entity, service, and automation hook when you’re ready for more.

---

## Explore deeper when you’re curious

| Want to… | Start here |
|----------|-----------|
| See the datasets and profiles that shape automations | [`custom_components/horticulture_assistant/data/`](custom_components/horticulture_assistant/data/README.md) |
| Validate your install or run maintenance helpers | [`scripts/`](scripts/README.md) |
| Dive into architecture notes, blueprints, and optional cloud extras | [`docs/`](docs/) |
| Share ideas, feature requests, or success stories | [Open an issue](https://github.com/DrZzs/Horticulture-Assistant-HASS-REPO/issues) |

MIT licensed. Crafted with the Home Assistant community for growers who want thriving plants without the guesswork. Happy cultivating!
