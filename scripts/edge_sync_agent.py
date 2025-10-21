"""Simple CLI entrypoint for the edge sync worker."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from aiohttp import ClientSession

from custom_components.horticulture_assistant.cloudsync import EdgeSyncStore, EdgeSyncWorker

_LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Horticulture Assistant edge sync agent")
    parser.add_argument("--db", type=Path, default=Path(".cloudsync.db"), help="SQLite path for sync state")
    parser.add_argument("--base-url", required=True, help="Cloud service base URL")
    parser.add_argument("--device-token", required=True, help="Device access token")
    parser.add_argument("--tenant-id", required=True, help="Tenant identifier")
    parser.add_argument("--interval", type=int, default=60, help="Poll interval in seconds")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    return parser.parse_args()


async def main_async(args: argparse.Namespace) -> None:
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    store = EdgeSyncStore(args.db)
    async with ClientSession() as session:
        worker = EdgeSyncWorker(store, session, args.base_url, args.device_token, args.tenant_id)
        _LOGGER.info("Starting edge sync loop")
        await worker.run_forever(interval_seconds=args.interval)


def main() -> None:
    args = parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:  # pragma: no cover - manual interruption
        _LOGGER.info("Sync agent stopped")


if __name__ == "__main__":
    main()
