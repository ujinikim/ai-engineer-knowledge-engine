"""Configured sources are authoritative for collection and visibility."""

from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache(maxsize=1)
def configured_sources() -> tuple[dict, ...]:
    source_file = Path(__file__).resolve().parents[2] / "data" / "update_sources.yml"
    with source_file.open("r", encoding="utf-8") as file:
        sources = yaml.safe_load(file)["sources"]
    required = {"slug", "name", "organization", "tool", "category", "source_kind", "feed_url", "homepage_url"}
    for source in sources:
        missing = required - source.keys()
        if missing:
            raise ValueError(f"Source {source.get('slug', '<unknown>')} is missing {sorted(missing)}")
    for field in ("slug", "feed_url"):
        values = [source[field] for source in sources]
        if len(values) != len(set(values)):
            raise ValueError(f"Duplicate {field} in update_sources.yml")
    return tuple(source for source in sources if source.get("enabled", True))


def configured_active_source_slugs() -> tuple[str, ...]:
    return tuple(source["slug"] for source in configured_sources())
