from contextlib import contextmanager

import pytest

from app.services.collector_lock import COLLECTOR_LOCK_NAME, collector_run_lock


class FakeConnection:
    def __init__(self, acquired: bool) -> None:
        self.acquired = acquired
        self.calls: list[tuple[str, dict]] = []

    def scalar(self, statement, parameters):
        self.calls.append((str(statement), parameters))
        if "pg_try_advisory_lock" in str(statement):
            return self.acquired
        return True


class FakeEngine:
    def __init__(self, acquired: bool) -> None:
        self.connection = FakeConnection(acquired)

    @contextmanager
    def connect(self):
        yield self.connection


def test_collector_lock_releases_an_acquired_lock() -> None:
    engine = FakeEngine(acquired=True)

    with collector_run_lock(engine) as acquired:
        assert acquired is True
        assert len(engine.connection.calls) == 1

    assert len(engine.connection.calls) == 2
    assert "pg_advisory_unlock" in engine.connection.calls[1][0]
    assert engine.connection.calls[1][1] == {"lock_name": COLLECTOR_LOCK_NAME}


def test_collector_lock_does_not_unlock_a_lock_owned_elsewhere() -> None:
    engine = FakeEngine(acquired=False)

    with collector_run_lock(engine) as acquired:
        assert acquired is False

    assert len(engine.connection.calls) == 1


def test_collector_lock_releases_after_collection_error() -> None:
    engine = FakeEngine(acquired=True)

    with pytest.raises(RuntimeError, match="collection failed"):
        with collector_run_lock(engine):
            raise RuntimeError("collection failed")

    assert len(engine.connection.calls) == 2
    assert "pg_advisory_unlock" in engine.connection.calls[1][0]
