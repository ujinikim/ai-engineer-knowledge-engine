"""Shared access to the configured update sources for command-line tools."""

from app.services.update_visibility import configured_sources


def load_update_sources() -> list[dict]:
    return list(configured_sources())


def update_source_map() -> dict[str, dict]:
    return {source["slug"]: source for source in load_update_sources()}
