"""Vocabulary and rules shared by ingestion, serving, and the database.

Pure definitions only: no database, model, or network imports, so any layer can use
them without depending on another layer.
"""

# Publication status of a stored article
PUBLISHED = "published"
QUARANTINED = "quarantined"

# Relevance routing; the feed and search show core articles unless asked for more
RELEVANCE_TIERS = ("core", "contextual", "excluded")

# Controlled taxonomy
PRIMARY_TOPICS = (
    "agentic-generative-ai",
    "machine-learning-classical-ai",
    "vision-speech-robotics",
    "data-search-retrieval",
    "ai-products-engineering-infrastructure",
    "safety-evaluation-governance",
)

EVENT_TYPES = (
    "release-update",
    "research",
    "guide",
    "analysis",
    "alert",
)


def visible_relevance_tiers(*, include_contextual: bool = False) -> tuple[str, ...]:
    return ("core", "contextual") if include_contextual else ("core",)


def compact_excerpt(text: str, limit: int = 420) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def article_excerpt(title: str, raw_text: str) -> str:
    """Card excerpt derived from stored text: the body after the title."""
    body = raw_text.removeprefix(title).strip() if title else raw_text
    return compact_excerpt(body or title)
