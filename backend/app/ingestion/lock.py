from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text


COLLECTOR_LOCK_NAME = "ai-engineer-knowledge-engine:update-collector"
_TRY_LOCK_SQL = text("SELECT pg_try_advisory_lock(hashtextextended(:lock_name, 0))")
_UNLOCK_SQL = text("SELECT pg_advisory_unlock(hashtextextended(:lock_name, 0))")


@contextmanager
def collector_run_lock(engine: Engine) -> Iterator[bool]:
    """Try to hold the process-wide collector lock for this context.

    PostgreSQL advisory locks belong to a database connection. Keeping this dedicated
    connection open makes the lock independent of the collector's transaction commits.
    PostgreSQL also releases it automatically if the process exits or disconnects.
    """
    with engine.connect() as connection:
        acquired = bool(
            connection.scalar(_TRY_LOCK_SQL, {"lock_name": COLLECTOR_LOCK_NAME})
        )
        try:
            yield acquired
        finally:
            if acquired:
                connection.scalar(_UNLOCK_SQL, {"lock_name": COLLECTOR_LOCK_NAME})
