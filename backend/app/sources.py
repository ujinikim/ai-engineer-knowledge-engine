"""Configured sources are authoritative for collection and visibility."""

from functools import lru_cache
from pathlib import Path
from typing import NotRequired, TypedDict

import yaml


class SourceConfig(TypedDict):
    """One entry of `data/update_sources.yml`, with every option the pipeline reads."""

    # Identity and display
    slug: str
    name: str
    organization: str
    tool: str
    homepage_url: str
    feed_url: str
    # What the source is and how much to trust it
    source_kind: str  # rss, atom, or html_listing
    source_type: NotRequired[str]  # official-engineering-blog, official-changelog, ...
    credibility_weight: NotRequired[float]  # feed ranking weight, default 1.0
    # Taxonomy defaults, used only when classification has no better evidence
    category: str
    default_primary_topic: NotRequired[str]
    default_event_types: NotRequired[list[str]]
    # Which entries to keep
    include_terms: NotRequired[list[str]]
    exclude_title_prefixes: NotRequired[list[str]]
    exclude_tags: NotRequired[list[str]]
    require_published_date: NotRequired[bool]
    # html_listing sources: which links on the listing page are articles
    link_pattern: NotRequired[str]
    # Full-article fetching and extraction
    fetch_full_article: NotRequired[bool]
    content_selector: NotRequired[str]
    date_selector: NotRequired[str]
    minimum_full_article_characters: NotRequired[int]


@lru_cache(maxsize=1)
def configured_sources() -> tuple[SourceConfig, ...]:
    source_file = Path(__file__).resolve().parents[1] / "data" / "update_sources.yml"
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
    return tuple(sources)


def configured_active_source_slugs() -> tuple[str, ...]:
    return tuple(source["slug"] for source in configured_sources())


def source_attribute(slug: str, key: str, default=None):
    """Read a per-source attribute from configuration instead of copying it into rows."""
    source = next((source for source in configured_sources() if source["slug"] == slug), None)
    return source.get(key, default) if source else default


def source_slugs_with(key: str, values: list[str], default=None) -> list[str]:
    return [
        source["slug"]
        for source in configured_sources()
        if source.get(key, default) in values
    ]


def sources_by_slug() -> dict[str, SourceConfig]:
    return {source["slug"]: source for source in configured_sources()}
