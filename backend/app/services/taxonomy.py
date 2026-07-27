import re


PRIMARY_TOPICS = (
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

EVENT_TYPES = (
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

MATURITY_LEVELS = (
    "stable",
    "general-availability",
    "beta",
    "preview",
    "release-candidate",
    "development",
    "research",
    "deprecated",
)

VERSIONED_LIBRARY_SOURCES = frozenset(
    {
        "langgraph",
        "litellm",
        "qdrant",
        "transformers",
        "vllm",
    }
)

RELEASE_EVENT_TYPES = frozenset(
    {
        "model-launch",
        "product-release",
        "library-release",
        "api-change",
        "integration",
    }
)

RC_VERSION_PATTERN = re.compile(
    r"(?<![a-z0-9])v?\d+(?:\.\d+)+(?:[-_.]?rc(?:[.-]?\d+)?)(?![a-z0-9])",
    re.IGNORECASE,
)


TOPIC_KEYWORDS = {
    "models-apis": (
        "model",
        "multimodal",
        "embedding",
        "api",
        "context window",
        "function calling",
    ),
    "agents-orchestration": (
        "agent",
        "mcp",
        "tool calling",
        "orchestration",
        "workflow",
        "memory",
    ),
    "inference-serving": (
        "inference",
        "serving",
        "quantization",
        "kv cache",
        "batching",
        "prefill",
        "throughput",
        "latency",
    ),
    "retrieval-data": (
        "retrieval",
        "rag",
        "rerank",
        "vector",
        "dataset",
        "indexing",
    ),
    "training-fine-tuning": (
        "training",
        "fine-tun",
        "distillation",
        "reinforcement learning",
        "post-training",
        "lora",
    ),
    "evaluation-observability": (
        "evaluation",
        "eval",
        "benchmark",
        "observability",
        "tracing",
        "monitoring",
    ),
    "developer-tools": (
        "coding agent",
        "copilot",
        "ide",
        "sdk",
        "cli",
        "developer tool",
    ),
    "infrastructure-hardware": (
        "gpu",
        "cuda",
        "kernel",
        "distributed",
        "cluster",
        "hardware",
        "accelerator",
    ),
    "safety-security": (
        "security",
        "safety",
        "vulnerability",
        "prompt injection",
        "jailbreak",
        "guardrail",
        "incident",
    ),
}


def classify_topic(text: str, default: str = "developer-tools") -> tuple[str, list[str]]:
    normalized = text.lower()
    scores = {
        topic: sum(normalized.count(keyword) for keyword in keywords)
        for topic, keywords in TOPIC_KEYWORDS.items()
    }
    ranked = sorted(scores, key=scores.get, reverse=True)
    primary = ranked[0] if scores[ranked[0]] > 0 else default
    tags = [topic for topic in ranked if topic != primary and scores[topic] > 0][:3]
    return primary if primary in PRIMARY_TOPICS else default, tags


def infer_event_types(text: str, default: list[str] | None = None) -> list[str]:
    normalized = text.lower()
    rules = {
        "model-launch": ("introducing", "new model", "model release"),
        "api-change": ("api", "endpoint", "responses api"),
        "integration": ("integration", "integrates with", "support for"),
        "research-result": ("paper", "research", "we propose"),
        "benchmark-result": ("benchmark", "state-of-the-art", "sota"),
        "pricing-change": ("pricing", "price", "billing"),
        "breaking-change": ("breaking change", "migration required"),
        "deprecation": ("deprecat", "sunset", "retir"),
        "security-issue": ("vulnerability", "security fix", "cve-"),
        "incident": ("incident", "outage"),
        "tutorial": ("tutorial", "how to", "step-by-step"),
    }
    matches = [event for event, terms in rules.items() if any(term in normalized for term in terms)]
    return list(dict.fromkeys((default or []) + matches))[:5]


def normalize_event_types(source_name: str, event_types: list[str]) -> list[str]:
    """Apply source-level event invariants after model classification."""
    normalized = list(dict.fromkeys(event_types))
    if source_name not in VERSIONED_LIBRARY_SOURCES:
        return normalized[:5]

    normalized = [
        event_type
        for event_type in normalized
        if event_type != "product-release"
        and not (source_name == "transformers" and event_type == "model-launch")
    ]
    if "library-release" not in normalized:
        normalized.insert(0, "library-release")
    return normalized[:5]


def infer_maturity(
    title: str,
    text: str = "",
    event_types: list[str] | None = None,
) -> str:
    value = f"{title} {text[:500]}".lower()
    if "deprecated" in value or "deprecation" in value or "sunset" in value:
        return "deprecated"
    if RC_VERSION_PATTERN.search(value):
        return "release-candidate"
    if "alpha" in value or "dev." in value or "development" in value:
        return "development"
    if "beta" in value:
        return "beta"
    if "preview" in value:
        return "preview"
    if "general availability" in value or re.search(r"\bga\b", value):
        return "general-availability"
    events = set(event_types or [])
    if (
        events.intersection({"research-result", "benchmark-result"})
        and not events.intersection(RELEASE_EVENT_TYPES)
    ):
        return "research"
    return "stable"


def clean_labels(values: object, allowed: tuple[str, ...], limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    labels = [str(value).strip().lower().replace("_", "-") for value in values]
    return [value for value in dict.fromkeys(labels) if value in allowed][:limit]


def clean_tags(values: object, limit: int = 8) -> list[str]:
    if not isinstance(values, list):
        return []
    tags = []
    for value in values:
        tag = re.sub(r"[^a-z0-9+#.]+", "-", str(value).strip().lower()).strip("-")
        if tag and tag not in tags:
            tags.append(tag)
    return tags[:limit]
