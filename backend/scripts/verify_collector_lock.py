import sys
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import engine
from app.services.collector_lock import COLLECTOR_LOCK_NAME, collector_run_lock


with collector_run_lock(engine) as first_acquired:
    if not first_acquired:
        raise RuntimeError("The first collector could not acquire an unused lock")

    with collector_run_lock(engine) as overlapping_acquired:
        if overlapping_acquired:
            raise RuntimeError("An overlapping collector acquired the same lock")

with collector_run_lock(engine) as acquired_after_release:
    if not acquired_after_release:
        raise RuntimeError("The collector lock was not reusable after release")

with engine.connect() as connection:
    connection.execute(text("SELECT 1"))

print(f"Collector advisory lock verified: {COLLECTOR_LOCK_NAME}")
