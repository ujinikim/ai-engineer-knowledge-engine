import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

import yaml

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal, engine
from app.services.collector_lock import collector_run_lock
from app.services.update_collector import UpdateCollectorService


SOURCE_FILE = Path(__file__).resolve().parents[1] / "data" / "update_sources.yml"


def load_sources(source_slugs: list[str] | None = None) -> list[dict]:
    with SOURCE_FILE.open("r", encoding="utf-8") as file:
        sources = yaml.safe_load(file)["sources"]
    if not source_slugs:
        return sources

    requested = set(source_slugs)
    selected = [source for source in sources if source["slug"] in requested]
    missing = sorted(requested - {source["slug"] for source in selected})
    if missing:
        raise ValueError(f"Unknown source slug(s): {', '.join(missing)}")
    return selected


async def collect_once(max_items: int, source_slugs: list[str] | None = None) -> bool:
    with collector_run_lock(engine) as acquired:
        if not acquired:
            print(json.dumps({"status": "skipped", "reason": "collection_already_running"}))
            return False

        with SessionLocal() as db:
            result = await UpdateCollectorService(db).collect(
                load_sources(source_slugs),
                max_items_per_source=max_items,
            )
        print(json.dumps({"status": "completed", **asdict(result)}, indent=2))
        return True


async def main(
    max_items: int,
    interval_minutes: int | None,
    source_slugs: list[str] | None = None,
) -> None:
    while True:
        await collect_once(max_items, source_slugs)
        if not interval_minutes:
            return
        print(f"Next collection in {interval_minutes} minutes.")
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
    asyncio.run(main(max(1, arguments.max_items), interval, arguments.source_slugs))
