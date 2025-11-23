"""CLI utilities for managing threshold approval records."""

from __future__ import annotations

import argparse

from ..engine.plant_engine.approval_queue import (apply_approved_thresholds,
                                         queue_threshold_updates)
from ..engine.plant_engine.utils import load_json


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    q = sub.add_parser("queue", help="queue threshold changes")
    q.add_argument("plant_id")
    q.add_argument("current", help="Path to current thresholds JSON")
    q.add_argument("proposed", help="Path to proposed thresholds JSON")

    a = sub.add_parser("apply", help="apply approved changes")
    a.add_argument("profile", help="Path to plant profile JSON")
    a.add_argument("pending", help="Path to pending changes JSON")

    args = parser.parse_args()

    if args.cmd == "queue":
        current = load_json(args.current)
        proposed = load_json(args.proposed)
        queue_threshold_updates(args.plant_id, current, proposed)
    else:  # apply
        apply_approved_thresholds(args.profile, args.pending)


if __name__ == "__main__":
    main()
