# Scripts Overview

Utility scripts help validate datasets, migrate schemas, and inspect runtime
artifacts. All scripts run offline against the data shipped in this repository.
Activate your Home Assistant virtual environment (or any Python 3.12+
interpreter) before executing them.

---

## Available Scripts

| Script | Description |
|--------|-------------|
| `validate_fertilizers_v3e.py` | Validates fertilizer detail files against the 2025-09-V3e schema. Runs in CI. |
| `validate_profiles.py` | Ensures bundled/local profiles follow expected structure and reports missing references. |
| `validate_logs.py` | Checks lifecycle JSONL logs for schema compliance and chronological order. |
| `migrate_fertilizer_schema.py` | Upgrades legacy fertilizer records to the latest schema version. Useful during dataset refreshes. |
| `sort_manifest.py` | Normalises dataset manifests and shard ordering to keep diffs readable. |
| `edge_sync_agent.py` | Example asyncio worker that exercises the cloud sync API using local outbox events. |

Scripts intentionally avoid external dependencies beyond those listed in
`requirements_test.txt`.

---

## Usage Examples

```bash
python scripts/validate_fertilizers_v3e.py
python scripts/validate_profiles.py --profiles custom_components/horticulture_assistant/data/local/profiles
python scripts/validate_logs.py --history custom_components/horticulture_assistant/history
python scripts/sort_manifest.py --dataset fertilizers/index_sharded
```

`edge_sync_agent.py` expects a running instance of the demo cloud API (see
`docs/cloud_edge_architecture.md`) and uses environment variables for auth
credentials.

Update this README whenever you add new tooling so reviewers know how to run it.
