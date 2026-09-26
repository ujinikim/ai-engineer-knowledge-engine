from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_CONFIG = BACKEND_DIR / "alembic.ini"


@lru_cache(maxsize=1)
def expected_alembic_heads() -> frozenset[str]:
    config = Config(str(ALEMBIC_CONFIG))
    script = ScriptDirectory.from_config(config)
    return frozenset(script.get_heads())


class ReadinessCheckError(Exception):
    def __init__(self, checks: dict[str, str]) -> None:
        super().__init__("Application dependencies are not ready.")
        self.checks = checks


class DatabaseReadinessChecker:
    def __init__(
        self,
        db: Session,
        expected_heads_provider: Callable[[], frozenset[str]] = expected_alembic_heads,
    ) -> None:
        self.db = db
        self.expected_heads_provider = expected_heads_provider

    def check(self) -> dict[str, str]:
        checks = {
            "database": "unavailable",
            "schema": "unknown",
            "vector": "unknown",
        }

        try:
            self.db.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            raise ReadinessCheckError(checks) from error
        checks["database"] = "reachable"

        try:
            version_table_exists = bool(
                self.db.scalar(text("SELECT to_regclass('public.alembic_version') IS NOT NULL"))
            )
            current_heads = (
                frozenset(self.db.scalars(text("SELECT version_num FROM alembic_version")).all())
                if version_table_exists
                else frozenset()
            )
            expected_heads = self.expected_heads_provider()
        except (CommandError, OSError, SQLAlchemyError) as error:
            checks["schema"] = "check_failed"
            raise ReadinessCheckError(checks) from error

        if not version_table_exists:
            checks["schema"] = "missing"
        elif current_heads != expected_heads:
            checks["schema"] = "out_of_date"
        else:
            checks["schema"] = "current"

        try:
            vector_installed = bool(
                self.db.scalar(
                    text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                )
            )
        except SQLAlchemyError as error:
            checks["vector"] = "check_failed"
            raise ReadinessCheckError(checks) from error

        checks["vector"] = "installed" if vector_installed else "missing"

        if checks["schema"] != "current" or checks["vector"] != "installed":
            raise ReadinessCheckError(checks)

        return checks
