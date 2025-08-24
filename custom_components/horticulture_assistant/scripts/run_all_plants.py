import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from plant_engine import run_daily_cycle
from plant_engine.utils import save_json

PLANT_DIR = "plants"
SUMMARY_PATH = "data/reports/summary.json"


def get_plant_ids():
    return [f.replace(".json", "") for f in os.listdir(PLANT_DIR) if f.endswith(".json")]


MAX_WORKERS = min(32, (os.cpu_count() or 1) * 2)


def _run_for_plant(plant_id: str) -> tuple[str, dict]:
    """Helper to execute :func:`run_daily_cycle` for a single plant."""

    print(f"🔄 Running daily engine for: {plant_id}")
    try:
        return plant_id, run_daily_cycle(plant_id)
    except Exception as exc:  # pragma: no cover - runtime safeguard
        print(f"❌ Error processing {plant_id}: {exc}")
        return plant_id, {"error": str(exc)}


def run_all_plants(parallel: bool = True) -> dict:
    """Run the daily engine for all plants and return summary."""

    summary: dict[str, dict] = {}
    plant_ids = get_plant_ids()

    if parallel and len(plant_ids) > 1:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            tasks = {executor.submit(_run_for_plant, pid): pid for pid in plant_ids}
            for future in as_completed(tasks):
                pid, result = future.result()
                summary[pid] = result
    else:
        for pid in plant_ids:
            pid, result = _run_for_plant(pid)
            summary[pid] = result

    # Save master report
    os.makedirs(os.path.dirname(SUMMARY_PATH), exist_ok=True)
    save_json(SUMMARY_PATH, summary)
    print(f"\n✅ Summary report written to {SUMMARY_PATH}")
    return summary


if __name__ == "__main__":
    run_all_plants()
