import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.update_visibility import source_attribute


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "feed_relevance_review_sample.json"
)
DEFAULT_DECISIONS = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "feed_relevance_review_decisions_2026-07-27.json"
)
TIERS = ("core", "contextual", "excluded")
REVIEW_VALUES = ("not_reviewed", "correct", "change_required", "uncertain")
IMPORTANT_EVENTS = {"security-issue", "incident", "breaking-change", "deprecation"}
CORE_EVENTS = {
    "model-launch",
    "product-release",
    "library-release",
    "api-change",
    "integration",
    "research-result",
    "benchmark-result",
    "pricing-change",
    "engineering-analysis",
    "tutorial",
}

# Human-reviewed taxonomy edge cases that also establish the initial relevance
# calibration set.
KNOWN_CONTEXTUAL_IDS = {
    "8c069ff1-0965-4aa8-bee0-a4fafe706d45": "funding_or_research_program",
    "4cfaf3ef-ab74-448f-a483-bb0b8a2f7153": "funding_or_research_program",
    "3a616afc-3e55-42c2-bbc5-fd9040b8c335": "funding_or_research_program",
    "a60a1b72-3bbf-4112-968e-cc1e692faead": "policy_or_legal_context",
    "1559e38f-57c2-46ec-a179-32e90824daed": "public_or_community_initiative",
}

INITIAL_REVIEW_DECISIONS = {
    "a00ef4de-86ce-402c-95f4-b59e8995e7fc": (
        "contextual",
        "Concrete adoption evidence includes 9,000 employees and a 30-minute "
        "incident-analysis result, but this is a customer case study rather than "
        "a technical update.",
    ),
    "cc7eac95-1c13-4893-aa71-99bede77edc0": (
        "contextual",
        "The conference announcement is not a release, but its detailed program "
        "contains relevant engineering sessions.",
    ),
    "339b61eb-6ccc-4834-84db-883b2ccb1c35": (
        "excluded",
        "Sparse internal-use marketing without implementation details, measured "
        "results, or a newly announced technical capability.",
    ),
    "db659e9e-071e-4e50-a4f0-6a50eef166aa": (
        "contextual",
        "The customer story contains concrete deployment scale and a measured lead "
        "recovery result, but it is not a product or engineering update.",
    ),
    "11387d03-5e7d-48ef-b2ef-8d4b1840767f": (
        "excluded",
        "Generic sales use-case list without a technical change, implementation, or "
        "measured engineering result.",
    ),
    "ea1c1631-32da-4a45-a891-d8c910fbbc0b": (
        "excluded",
        "Generic data-science use-case list without substantive implementation or "
        "a new technical capability.",
    ),
    "9869a08c-92e7-4382-8472-e2de6e6b3968": (
        "excluded",
        "Beginner product onboarding rather than AI-engineering material.",
    ),
    "8ed7132e-97b1-4da0-aa7a-d11e1675c8a2": (
        "core",
        "Despite the promotional title, the excerpt announces ChatGPT Work as a "
        "new agent capability that acts across apps and files.",
    ),
    "c086bd9f-d93d-48dd-bae2-5af03cf7b6f0": (
        "excluded",
        "Sparse promotional customer story without architecture, implementation "
        "detail, or concrete technical evidence.",
    ),
    "305ec815-1f2f-4020-8e2c-0d13c74e16a1": (
        "core",
        "The excerpt identifies concrete ChatGPT safety capabilities, including "
        "age-appropriate protections, learning tools, and parental controls. It "
        "remains hidden separately because only a sparse feed excerpt was extracted.",
    ),
    "22ced16c-ce30-4651-af1f-ac407b520fe5": (
        "core",
        "The article teaches readers how to use the existing TensorRT "
        "IProgressMonitor API, so technical_tutorial is the principal relevance "
        "reason rather than a new library release.",
    ),
    "eb7bd945-34ce-4846-a45b-d313e9450553": (
        "core",
        "The article's principal evidence is a measured CVDP benchmark result, so "
        "research_or_benchmark is more precise than generic engineering analysis.",
    ),
    "35c47f41-d540-42c2-a31a-3126cbbe79cf": (
        "core",
        "General availability of GPT-5.6 models on Amazon Bedrock is the principal "
        "event, making technical_release_or_change the primary relevance reason.",
    ),
}

TITLE_OVERRIDES = {
    "pytorch conference north america schedule is live": (
        "contextual",
        ["event_or_community_update"],
        0.95,
    ),
    "google deepmind and a24 announce first-of-its-kind research partnership": (
        "contextual",
        ["business_or_partnership_context"],
        0.95,
    ),
    "how sales teams use chatgpt work": (
        "excluded",
        ["customer_story_or_case_study"],
        0.95,
    ),
    "how codex became a collaborator for openai’s creative team": (
        "excluded",
        ["customer_story_or_case_study"],
        0.95,
    ),
    "how to manage ai investments in the agentic era": (
        "contextual",
        ["general_strategy_or_societal_context"],
        0.90,
    ),
    "why teens deserve access to safe ai": (
        "core",
        ["technical_release_or_change"],
        0.88,
    ),
    "chatgpt is now a partner for your most ambitious work": (
        "core",
        ["technical_release_or_change"],
        0.90,
    ),
    "ntt data group cuts incident analysis to 30 minutes with codex": (
        "contextual",
        ["measured_customer_deployment"],
        0.92,
    ),
    "getting started with chatgpt": (
        "excluded",
        ["generic_getting_started_content"],
        0.92,
    ),
    "building ai infrastructure with the effingham county community": (
        "contextual",
        ["public_or_community_initiative"],
        0.90,
    ),
    "australian payments plus moves faster with chatgpt and codex": (
        "excluded",
        ["customer_story_or_case_study"],
        0.90,
    ),
    "how cars24 scales conversations and builds faster with openai": (
        "contextual",
        ["measured_customer_deployment"],
        0.92,
    ),
    "how data science teams use chatgpt work": (
        "excluded",
        ["customer_story_or_case_study"],
        0.90,
    ),
    "introducing the chatgpt for small business program": (
        "contextual",
        ["business_or_partnership_context"],
        0.85,
    ),
    "make long-running nvidia tensorrt engine builds observable and cancelable in python or c++": (
        "core",
        ["technical_tutorial"],
        0.92,
    ),
    "nvidia nemotron 3 ultra leads open models on accuracy and efficiency in agentic rtl coding": (
        "core",
        ["research_or_benchmark"],
        0.92,
    ),
    "get started with openai gpt-5.6 sol, terra, and luna on amazon bedrock": (
        "core",
        ["technical_release_or_change"],
        0.95,
    ),
}


def recommendation(document: Document) -> tuple[str, list[str], float]:
    document_id = str(document.id)
    title = str(document.title or "").strip()
    normalized_title = title.lower()
    event_types = set(document.event_types or [])

    if document_id in KNOWN_CONTEXTUAL_IDS:
        return "contextual", [KNOWN_CONTEXTUAL_IDS[document_id]], 0.98
    if normalized_title in TITLE_OVERRIDES:
        return TITLE_OVERRIDES[normalized_title]

    if re.search(r"\b(webinar|conference|summit|schedule is live|join us)\b", normalized_title):
        return "excluded", ["event_promotion"], 0.86
    if re.search(
        r"^(how .+ (uses?|use|scales?|builds?|moves?)|customer story\b)",
        normalized_title,
    ):
        return "excluded", ["customer_story_or_case_study"], 0.82
    if re.search(r"\b(fund|funding|investment|research agenda)\b", normalized_title):
        return "contextual", ["funding_or_research_program"], 0.86
    if re.search(r"\b(court|legal|lawsuit|regulation|policy ruling)\b", normalized_title):
        return "contextual", ["policy_or_legal_context"], 0.84
    if (
        "partnership" in normalized_title
        and not event_types.intersection({"integration", "security-issue"})
    ):
        return "contextual", ["business_or_partnership_context"], 0.82

    if event_types.intersection(IMPORTANT_EVENTS):
        return "core", ["security_or_operational_event"], 0.97
    if event_types.intersection({"model-launch", "product-release", "library-release", "api-change", "integration"}):
        return "core", ["technical_release_or_change"], 0.90
    if event_types.intersection({"research-result", "benchmark-result"}):
        return "core", ["research_or_benchmark"], 0.90
    if "engineering-analysis" in event_types:
        return "core", ["engineering_analysis"], 0.85
    if "tutorial" in event_types:
        return "core", ["technical_tutorial"], 0.82
    return "contextual", ["unclear_engineering_relevance"], 0.55


def review_key(document: Document, tier: str, reasons: list[str]) -> str:
    payload = json.dumps(
        {
            "content_hash": document.content_hash,
            "recommended_tier": tier,
            "recommended_reasons": reasons,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def existing_reviews(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        str(item["review_key"]): item
        for item in payload.get("items", [])
        if item.get("review_key")
    }


def recorded_decisions(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        str(item["review_key"]): item
        for item in payload.get("decisions", [])
        if item.get("review_key")
    }


def select_sample(items: list[dict], sample_size: int) -> list[dict]:
    selected: list[dict] = []
    seen: set[str] = set()
    seen_content: set[tuple[str, str]] = set()

    def add(item: dict) -> None:
        content_key = (item["source_name"], item["title"].strip().lower())
        if (
            len(selected) < sample_size
            and item["document_id"] not in seen
            and content_key not in seen_content
        ):
            selected.append(item)
            seen.add(item["document_id"])
            seen_content.add(content_key)

    # Start with all high-value edge cases and proposed non-core records.
    for item in items:
        if item["document_id"] in KNOWN_CONTEXTUAL_IDS:
            add(item)
    for item in items:
        if item["document_id"] in INITIAL_REVIEW_DECISIONS:
            add(item)
    for tier, limit in (("excluded", 12), ("contextual", 13)):
        added = 0
        for item in items:
            if item["recommended_tier"] == tier and added < limit:
                before = len(selected)
                add(item)
                added += len(selected) - before

    # Include one control from every source.
    for source_name in sorted({item["source_name"] for item in items}):
        candidate = next(
            (item for item in items if item["source_name"] == source_name),
            None,
        )
        if candidate:
            add(candidate)

    # Cover each present event type and fill with core controls.
    event_types = sorted(
        {
            event_type
            for item in items
            for event_type in item["taxonomy"]["event_types"]
        }
    )
    for event_type in event_types:
        candidate = next(
            (
                item
                for item in items
                if event_type in item["taxonomy"]["event_types"]
            ),
            None,
        )
        if candidate:
            add(candidate)
    for item in items:
        if item["recommended_tier"] == "core":
            add(item)
    for item in items:
        add(item)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a stratified human review for default-feed relevance."
    )
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    arguments = parser.parse_args()

    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prior_reviews = existing_reviews(output)
    prior_reviews.update(recorded_decisions(arguments.decisions.resolve()))

    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(Document)
                .order_by(
                    Document.published_at.desc().nullslast(),
                    Document.source_name,
                    Document.id,
                )
            )
        )

    corpus_counts: Counter[str] = Counter()
    all_items: list[dict] = []
    for document in documents:
        tier, reasons, confidence = recommendation(document)
        corpus_counts[tier] += 1
        key = review_key(document, tier, reasons)
        prior = prior_reviews.get(key, {})
        initial_decision = INITIAL_REVIEW_DECISIONS.get(str(document.id))
        if initial_decision and initial_decision[0] != tier:
            raise ValueError(
                f"Initial relevance decision for {document.id} expected "
                f"{initial_decision[0]}, recommendation produced {tier}"
            )
        prior_review = str(prior.get("relevance_review") or "not_reviewed")
        review = (
            "correct"
            if initial_decision and prior_review == "not_reviewed"
            else prior_review
        )
        if review not in REVIEW_VALUES:
            review = "not_reviewed"
        initial_note = initial_decision[1] if initial_decision else ""
        all_items.append(
            {
                "document_id": str(document.id),
                "review_key": key,
                "source_name": document.source_name,
                "source_type": source_attribute(document.source_name, "source_type"),
                "title": document.title,
                "url": document.url,
                "published_at": (
                    document.published_at.isoformat()
                    if document.published_at
                    else None
                ),
                "recommended_tier": tier,
                "recommended_reasons": reasons,
                "recommendation_confidence": confidence,
                "current_visibility": {
                    "extraction_status": document.extraction_status,
                },
                "taxonomy": {
                    "primary_topic": document.primary_topic,
                    "event_types": list(document.event_types or []),
                },
                "generated_card": {
                    "display_headline": document.display_headline,
                    "summary": document.summary,
                    "why_it_matters": document.why_it_matters,
                    "key_points": list(document.key_points or []),
                },
                "relevance_review": review,
                "reviewed_tier": prior.get("reviewed_tier"),
                "reviewed_reasons": list(prior.get("reviewed_reasons") or []),
                "relevance_notes": str(
                    prior.get("relevance_notes") or initial_note
                ),
            }
        )

    sampled_items = select_sample(all_items, max(0, arguments.sample_size))
    sample_counts = Counter(item["recommended_tier"] for item in sampled_items)
    sampled_ids = {item["document_id"] for item in sampled_items}
    calibration_complete = all(
        item["relevance_review"] not in {"not_reviewed", "uncertain"}
        for item in sampled_items
    )
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "policy_status": (
            "calibration_complete_not_applied"
            if calibration_complete
            else "proposal_for_human_calibration"
        ),
        "decisions_file": str(arguments.decisions.resolve()),
        "instructions": {
            "core": "Show in the default AI-engineering feed.",
            "contextual": (
                "Retain and search, but show only through an Industry context filter."
            ),
            "excluded": (
                "Hide from normal feed/search; retain for provenance and diagnostics."
            ),
            "review_fields": {
                "relevance_review": list(REVIEW_VALUES),
                "reviewed_tier": list(TIERS),
                "reviewed_reasons": "Controlled reason labels or an empty list.",
                "relevance_notes": "Short rationale, especially for changes or uncertainty.",
            },
        },
        "corpus_summary": {
            "documents": len(all_items),
            "recommended_tier_counts": dict(corpus_counts),
        },
        "sample_summary": {
            "items": len(sampled_items),
            "recommended_tier_counts": dict(sample_counts),
            "review_status_counts": dict(
                Counter(item["relevance_review"] for item in sampled_items)
            ),
            "sources_covered": len(
                {item["source_name"] for item in sampled_items}
            ),
        },
        "items": sampled_items,
        "corpus_assignment_index": [
            {
                "document_id": item["document_id"],
                "source_name": item["source_name"],
                "title": item["title"],
                "recommended_tier": item["recommended_tier"],
                "recommended_reasons": item["recommended_reasons"],
                "sampled_for_review": item["document_id"] in sampled_ids,
            }
            for item in all_items
        ],
        "change_history": [
            {
                "date": "2026-07-26",
                "change": (
                    "Created the initial three-tier feed-relevance calibration "
                    "sample after taxonomy regression passed."
                ),
            }
        ],
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Corpus documents: {len(all_items)}")
    print(f"Corpus recommendations: {dict(corpus_counts)}")
    print(f"Review items: {len(sampled_items)}")
    print(f"Sample recommendations: {dict(sample_counts)}")
    print(f"Sources covered: {payload['sample_summary']['sources_covered']}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
