import argparse
import asyncio
import logging
import sys
import time
import uuid
from dataclasses import asdict
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from scripts._source_config import load_update_sources
from app.core.settings import settings
from app.core.structured_logging import get_logger, log_event
from app.db.session import SessionLocal, engine
from app.services.collector_lock import collector_run_lock
from app.services.update_collector import UpdateCollectorService


logger = get_logger("collector.runner")


class CollectionRunFailed(RuntimeError):
    pass


def load_sources(source_slugs: list[str] | None = None) -> list[dict]:
    sources = load_update_sources()
    if not source_slugs:
        return [source for source in sources if source.get("enabled", True)]

    requested = set(source_slugs)
    selected = [source for source in sources if source["slug"] in requested]
    missing = sorted(requested - {source["slug"] for source in selected})
    if missing:
        raise ValueError(f"Unknown source slug(s): {', '.join(missing)}")
    return selected


async def collect_once(max_items: int, source_slugs: list[str] | None = None) -> bool:
    run_id = uuid.uuid4().hex
    started = time.perf_counter()
    try:
        with collector_run_lock(engine) as acquired:
            if not acquired:
                log_event(
                    logger,
                    "collection_skipped",
                    run_id=run_id,
                    reason="collection_already_running",
                    duration_ms=int((time.perf_counter() - started) * 1000),
                )
                return False

            sources = load_sources(source_slugs)
            log_event(
                logger,
                "collection_started",
                run_id=run_id,
                configured_sources=len(sources),
                max_items_per_source=max_items,
            )
            with SessionLocal() as db:
                result = await UpdateCollectorService(db).collect(
                    sources,
                    max_items_per_source=max_items,
                    run_id=run_id,
                )
            fields = asdict(result)
            status = (
                "success"
                if result.errors == 0
                else "partial_success"
                if result.sources_processed > 0
                else "failed"
            )
            log_event(
                logger,
                "collection_completed",
                level=logging.ERROR if status == "failed" else logging.INFO,
                run_id=run_id,
                status=status,
                duration_ms=int((time.perf_counter() - started) * 1000),
                chat_model=settings.chat_model,
                embedding_model=settings.embedding_model,
                **fields,
            )
            if status == "failed":
                raise CollectionRunFailed
            return True
    except Exception as error:
        log_event(
            logger,
            "collection_failed",
            level=logging.ERROR,
            run_id=run_id,
            exception_type=type(error).__name__,
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        raise


async def main(
    max_items: int,
    interval_minutes: int | None,
    source_slugs: list[str] | None = None,
) -> None:
    while True:
        await collect_once(max_items, source_slugs)
        if not interval_minutes:
            return
        log_event(logger, "collection_waiting", interval_minutes=interval_minutes)
        await asyncio.sleep(interval_minutes * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect official developer-tool release feeds.")
    parser.add_argument("--max-items", type=int, default=12, help="Maximum entries per source")
    parser.add_argument(
        "--interval-minutes",
        type=int,
        help="Keep running and collect again after this interval",
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="source_slugs",
        help="Collect one source slug; repeat to select multiple sources",
    )
    arguments = parser.parse_args()
    interval = max(1, arguments.interval_minutes) if arguments.interval_minutes else None
    try:
        asyncio.run(main(max(1, arguments.max_items), interval, arguments.source_slugs))
    except Exception:
        raise SystemExit(1) from None
