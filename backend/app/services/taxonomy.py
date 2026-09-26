import re


TAXONOMY_POLICY_VERSION = "2026-09-12-v2"

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

# Existing rows remain readable while taxonomy v2 is rolled out by backfill.
LEGACY_PRIMARY_TOPICS = (
    "models-apis",
    "agents-orchestration",
    "inference-serving",
    "retrieval-data",
    "training-fine-tuning",
    "evaluation-observability",
    "developer-tools",
    "infrastructure-hardware",
    "safety-security",
)

LEGACY_EVENT_TYPES = (
    "model-launch",
    "product-release",
    "library-release",
    "api-change",
    "integration",
    "research-result",
    "benchmark-result",
    "pricing-change",
    "breaking-change",
    "deprecation",
    "security-issue",
    "incident",
    "engineering-analysis",
    "tutorial",
)

SOURCE_TYPES = (
    "official-release",
    "official-changelog",
    "official-engineering-blog",
    "official-product-news",
    "research-paper",
    "editorial-analysis",
    "community-signal",
)

TOPIC_KEYWORDS = {
    "agentic-generative-ai": (
        "agent",
        "agentic",
        "foundation model",
        "generative ai",
        "language model",
        "llm",
        "mcp",
        "prompt",
        "tool calling",
        "orchestration",
    ),
    "machine-learning-classical-ai": (
        "machine learning",
        "deep learning",
        "training",
        "fine-tun",
        "distillation",
        "reinforcement learning",
        "neural network",
        "optimization",
        "recommendation system",
        "forecasting",
        "symbolic ai",
    ),
    "vision-speech-robotics": (
        "computer vision",
        "image generation",
        "video generation",
        "speech recognition",
        "text-to-speech",
        "audio model",
        "multimodal",
        "robot",
        "embodied ai",
    ),
    "data-search-retrieval": (
        "retrieval",
        "rag",
        "rerank",
        "embedding",
        "vector database",
        "knowledge graph",
        "dataset",
        "indexing",
        "information retrieval",
        "web retrieval",
        "vector search",
        "search index",
        "search engine",
        "retrieval system",
    ),
    "ai-products-engineering-infrastructure": (
        "api",
        "sdk",
        "copilot",
        "developer tool",
        "inference",
        "serving",
        "deployment",
        "observability",
        "gpu",
        "cuda",
        "distributed",
        "cluster",
        "hardware",
        "latency",
        "throughput",
    ),
    "safety-evaluation-governance": (
        "evaluation",
        "eval",
        "benchmark",
        "security",
        "safety",
        "vulnerability",
        "alignment",
        "interpretability",
        "governance",
        "policy",
        "privacy",
        "incident",
    ),
}


def classify_topic(
    text: str,
    default: str = "ai-products-engineering-infrastructure",
) -> tuple[str, list[str]]:
    """Choose one broad category; the empty tag list is retained for API compatibility."""
    primary, _ = classify_topic_with_method(text, default)
    return primary, []


def classify_topic_with_method(
    text: str,
    default: str = "ai-products-engineering-infrastructure",
) -> tuple[str, str]:
    """Choose one category and expose whether evidence or the source default decided it."""
    normalized = text.lower()
    scores = {
        topic: sum(_keyword_count(normalized, keyword) for keyword in keywords)
        for topic, keywords in TOPIC_KEYWORDS.items()
    }
    ranked = sorted(scores, key=scores.get, reverse=True)
    safe_default = default if default in PRIMARY_TOPICS else "ai-products-engineering-infrastructure"
    if scores[ranked[0]] > 0:
        return ranked[0], "deterministic-keyword"
    return safe_default, "source-default"


def _keyword_count(text: str, keyword: str) -> int:
    if keyword.replace("-", "").isalnum():
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text))
    return text.count(keyword)


def infer_event_types(text: str, default: list[str] | None = None) -> list[str]:
    """Choose at most one broad event, using the source default only as a fallback."""
    normalized = text.lower()
    rules = (
        (
            "alert",
            (
                "vulnerability",
                "security fix",
                "cve-",
                "incident",
                "outage",
                "breaking change",
                "deprecat",
                "sunset",
            ),
        ),
        ("research", ("research", "paper", "we propose", "study", "benchmark result")),
        ("guide", ("tutorial", "how to", "step-by-step", "walkthrough", "guide")),
        (
            "release-update",
            (
                "introducing",
                "launch",
                "released",
                "release",
                "now available",
                "api change",
                "integration",
            ),
        ),
        ("analysis", ("analysis", "technical deep dive", "explainer")),
    )
    for event, terms in rules:
        if any(term in normalized for term in terms):
            return [event]
    return clean_labels(default, EVENT_TYPES, limit=1)


def normalize_event_types(source_name: str, event_types: list[str]) -> list[str]:
    """Normalize the compatibility array to zero or one taxonomy-v2 event."""
    del source_name
    return clean_labels(event_types, EVENT_TYPES, limit=1)


def clean_labels(values: object, allowed: tuple[str, ...], limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    labels = [str(value).strip().lower().replace("_", "-") for value in values]
    return [value for value in dict.fromkeys(labels) if value in allowed][:limit]
