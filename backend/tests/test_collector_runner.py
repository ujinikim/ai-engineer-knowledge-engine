import asyncio
import json
from contextlib import contextmanager, nullcontext

import pytest

from app.services.update_collector import CollectionResult
from scripts import collect_updates


def events(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def install_runner_fakes(monkeypatch, result: CollectionResult) -> None:
    @contextmanager
    def acquired_lock(_engine):
        yield True

    class FakeCollector:
        def __init__(self, _db) -> None:
            pass

        async def collect(self, _sources, max_items_per_source, run_id):
            return result

    monkeypatch.setattr(collect_updates, "collector_run_lock", acquired_lock)
    monkeypatch.setattr(collect_updates, "load_sources", lambda _slugs: [{"slug": "source"}])
    monkeypatch.setattr(collect_updates, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(collect_updates, "UpdateCollectorService", FakeCollector)


def test_overlapping_collection_is_a_successful_skip(monkeypatch, capsys) -> None:
    @contextmanager
    def unavailable_lock(_engine):
        yield False

    monkeypatch.setattr(collect_updates, "collector_run_lock", unavailable_lock)

    assert asyncio.run(collect_updates.collect_once(12)) is False
    log_events = events(capsys.readouterr().out)

    assert [event["event"] for event in log_events] == ["collection_skipped"]
    assert log_events[0]["reason"] == "collection_already_running"


def test_partial_collection_is_reported_without_failing_process(monkeypatch, capsys) -> None:
    install_runner_fakes(
        monkeypatch,
        CollectionResult(sources_processed=1, updates_created=2, chunks_written=3, errors=1),
    )

    assert asyncio.run(collect_updates.collect_once(12)) is True
    completed = next(
        event
        for event in events(capsys.readouterr().out)
        if event["event"] == "collection_completed"
    )

    assert completed["status"] == "partial_success"
    assert completed["updates_created"] == 2
    assert completed["chunks_written"] == 3


def test_all_source_failure_marks_the_job_failed(monkeypatch, capsys) -> None:
    install_runner_fakes(monkeypatch, CollectionResult(errors=2))

    with pytest.raises(collect_updates.CollectionRunFailed):
        asyncio.run(collect_updates.collect_once(12))

    log_events = events(capsys.readouterr().out)
    assert any(
        event["event"] == "collection_completed" and event["status"] == "failed"
        for event in log_events
    )
    assert any(
        event["event"] == "collection_failed"
        and event["exception_type"] == "CollectionRunFailed"
        for event in log_events
    )
