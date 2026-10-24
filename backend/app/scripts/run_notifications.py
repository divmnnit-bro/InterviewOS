"""Notification worker: create missing booking notifications, then deliver pending/failed ones.

    python -m app.scripts.run_notifications          # loop forever, every 15 seconds
    python -m app.scripts.run_notifications --once   # one pass (for cron or tests)
Safe to run several copies: rows are claimed with FOR UPDATE SKIP LOCKED.
"""
from __future__ import annotations

import logging
import sys
import time

from app.db.database import SessionLocal
from app.services import notifications

log = logging.getLogger("notifications")


def run_once() -> dict[str, int]:
    with SessionLocal() as db:
        created = notifications.backfill_missing(db)
    with SessionLocal() as db:
        stats = notifications.deliver_pending(db)
    stats["backfilled"] = created
    return stats


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO)
    if "--once" in argv:
        print(run_once())
        return 0
    while True:
        try:
            stats = run_once()
            if any(stats.values()):
                log.info("pass done: %s", stats)
        except Exception:
            log.exception("notification pass failed; will retry")
        time.sleep(15)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
