import asyncio
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes import get_readiness_checker
from app.core.settings import Settings
from app.main import create_app
from app.services.health import (
    DatabaseReadinessChecker,
    ReadinessCheckError,
    expected_alembic_heads,
)


EXPECTED_HEAD = "20260925_0006"


class StubReadinessChecker:
    def __init__(self, checks: dict[str, str], *, fail: bool = False) -> None:
        self.checks = checks
        self.fail = fail

    def check(self) -> dict[str, str]:
        if self.fail:
            raise ReadinessCheckError(self.checks)
        return self.checks


def get_response(application: FastAPI, path: str) -> Response:
    async def request() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://health-test") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_liveness_and_legacy_health_do_not_require_database() -> None:
    application = create_app(Settings(_env_file=None, app_environment="test"))

    legacy_response = get_response(application, "/health")
    live_response = get_response(application, "/health/live")

    assert legacy_response.status_code == 200
    assert legacy_response.json() == {"status": "ok"}
    assert live_response.status_code == 200
    assert live_response.json() == {"status": "alive"}


def test_api_prefix_preserves_health_routes_for_cloudfront() -> None:
    application = create_app(Settings(_env_file=None, app_environment="test"))

    legacy_response = get_response(application, "/api/health")
    live_response = get_response(application, "/api/health/live")

    assert legacy_response.status_code == 200
    assert live_response.status_code == 200
    assert "/api/updates" in application.openapi()["paths"]
    assert "/api/ask" in application.openapi()["paths"]


def test_ready_endpoint_returns_dependency_checks() -> None:
    application = create_app(Settings(_env_file=None, app_environment="test"))
    checker = StubReadinessChecker(
        {"database": "reachable", "schema": "current", "vector": "installed"}
    )
    application.dependency_overrides[get_readiness_checker] = lambda: checker

    response = get_response(application, "/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {"database": "reachable", "schema": "current", "vector": "installed"},
    }


def test_not_ready_endpoint_returns_503_without_exception_details() -> None:
    application = create_app(Settings(_env_file=None, app_environment="test"))
    checker = StubReadinessChecker(
        {"database": "unavailable", "schema": "unknown", "vector": "unknown"}, fail=True
    )
    application.dependency_overrides[get_readiness_checker] = lambda: checker

    response = get_response(application, "/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable", "schema": "unknown", "vector": "unknown"},
    }


def make_database_session(
    *, version_table_exists: bool = True, current_heads: list[str] | None = None, vector=True
) -> Mock:
    db = Mock(spec=Session)
    db.scalar.side_effect = [version_table_exists, vector]
    db.scalars.return_value.all.return_value = current_heads or [EXPECTED_HEAD]
    return db


def test_database_readiness_accepts_current_migrated_pgvector_schema() -> None:
    db = make_database_session()
    checker = DatabaseReadinessChecker(db, lambda: frozenset({EXPECTED_HEAD}))

    assert checker.check() == {
        "database": "reachable",
        "schema": "current",
        "vector": "installed",
    }


@pytest.mark.parametrize(
    ("db", "expected_checks"),
    [
        (
            make_database_session(current_heads=["older_revision"]),
            {"database": "reachable", "schema": "out_of_date", "vector": "installed"},
        ),
        (
            make_database_session(version_table_exists=False),
            {"database": "reachable", "schema": "missing", "vector": "installed"},
        ),
        (
            make_database_session(vector=False),
            {"database": "reachable", "schema": "current", "vector": "missing"},
        ),
    ],
)
def test_database_readiness_rejects_incomplete_dependencies(
    db: Mock, expected_checks: dict[str, str]
) -> None:
    checker = DatabaseReadinessChecker(db, lambda: frozenset({EXPECTED_HEAD}))

    with pytest.raises(ReadinessCheckError) as error:
        checker.check()

    assert error.value.checks == expected_checks


def test_database_readiness_hides_connection_exception() -> None:
    db = Mock(spec=Session)
    db.execute.side_effect = SQLAlchemyError("secret database connection details")
    checker = DatabaseReadinessChecker(db, lambda: frozenset({EXPECTED_HEAD}))

    with pytest.raises(ReadinessCheckError) as error:
        checker.check()

    assert error.value.checks == {
        "database": "unavailable",
        "schema": "unknown",
        "vector": "unknown",
    }
    assert "secret" not in str(error.value)


def test_packaged_alembic_head_is_the_expected_revision() -> None:
    assert expected_alembic_heads() == frozenset({EXPECTED_HEAD})
