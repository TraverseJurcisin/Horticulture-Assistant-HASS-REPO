# Scripts Overview

Utility scripts ship with the repository to keep datasets healthy and to aid migration tasks. All scripts are safe to run locally—they rely only on the data bundled with the repo.

## Key Scripts

| Script | Description |
|--------|-------------|
| `validate_profiles.py` | Ensures bundled/local profiles follow expected structure and that required keys are present. |
| `validate_fertilizers_v3e.py` | Validates fertilizer detail files against the 2025-09-V3e schema (runs in CI). |
| `migrate_fertilizer_schema.py` | Migrates legacy fertilizer detail records into the latest schema version. Useful when upstream data sources change. |
| `fertilizer_search.py` | CLI utility for searching the fertilizer dataset and printing formatted summaries. |
| `edge_sync_agent.py` | Minimal asyncio loop that posts local outbox events to the cloud service and pulls library/stat deltas. |

## Running Scripts

Use your Home Assistant virtual environment or any Python 3.12+ interpreter:

```bash
python scripts/validate_fertilizers_v3e.py
python scripts/validate_profiles.py
```

Scripts intentionally avoid external dependencies beyond those listed in `requirements_test.txt`. If you introduce new helpers, document them here and ensure they work offline.
