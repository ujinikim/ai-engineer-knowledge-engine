import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import yaml
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.article_summary import ArticleSummaryService
from app.services.summary_quality import SummaryQualityService


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "eval"
    / "summaries"
    / "sparse_prompt_regression.json"
)
SOURCE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "update_sources.yml"
TARGETS = {
    "ollama": "v0.32.0-rc0",
    "langgraph": "langgraph==1.2.9",
    "vllm": "v0.24.0rc2: Fix P/D with DP Supervisor (#46628)",
    "qdrant": "v1.18.3",
}


def source_configs() -> dict[str, dict]:
    payload = yaml.safe_load(SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))
    return {item["slug"]: item for item in payload["sources"]}


def load_target_documents() -> dict[str, Document]:
    documents: dict[str, Document] = {}
    with SessionLocal() as db:
        for source_name, title in TARGETS.items():
            document = db.scalar(
                select(Document).where(
                    Document.source_name == source_name,
                    Document.title == title,
                )
            )
            if document is None:
                raise RuntimeError(f"Missing regression document: {source_name} / {title}")
            db.expunge(document)
            documents[source_name] = document
    return documents


def evaluation_document(document: Document, metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(
        id=document.id,
        content_hash=document.content_hash,
        source_name=document.source_name,
        source_type=document.source_type,
        title=document.title,
        url=document.url,
        canonical_url=document.canonical_url,
        raw_text=document.raw_text,
        doc_metadata=metadata,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview the sparse-source summary prompt without updating stored documents."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--change-note",
        default=(
            "Compared stored pre-change summaries with read-only generations from the "
            "sparse-source prompt revision."
        ),
    )
    arguments = parser.parse_args()

    configs = source_configs()
    documents = load_target_documents()
    summarizer = ArticleSummaryService()
    evaluator = SummaryQualityService()
    if summarizer.client is None:
        raise RuntimeError("OPENAI_API_KEY is required for the prompt regression preview.")

    cases = []
    for source_name, title in TARGETS.items():
        document = documents[source_name]
        config = configs[source_name]
        before_metadata = dict(document.doc_metadata or {})
        before_evaluation = evaluator.evaluate(
            evaluation_document(document, before_metadata)
        )
        after_summary = summarizer.summarize(
            title=document.title,
            raw_text=document.raw_text,
            organization=config["organization"],
            tool=config["tool"],
            source_type=config["source_type"],
            default_topic=config["default_primary_topic"],
            default_event_types=config["default_event_types"],
        )
        after_metadata = {**before_metadata, **after_summary.metadata()}
        after_evaluation = evaluator.evaluate(
            evaluation_document(document, after_metadata)
        )
        cases.append(
            {
                "source_name": source_name,
                "title": title,
                "url": document.canonical_url or document.url,
                "source_detail_level": summarizer._source_detail_level(
                    document.title, document.raw_text
                ),
                "before": {
                    "generated_summary": {
                        field: before_metadata.get(field)
                        for field in (
                            "display_headline",
                            "summary",
                            "why_it_matters",
                            "key_points",
                            "primary_topic",
                            "topic_tags",
                            "event_types",
                            "entity_tags",
                            "maturity",
                        )
                    },
                    "automated_status": before_evaluation.quality_status,
                    "warnings": before_evaluation.warnings,
                    "grounding_overlap": before_evaluation.grounding_overlap,
                    "unsupported_numbers": before_evaluation.unsupported_numbers,
                },
                "after": {
                    "generated_summary": {
                        field: after_summary.metadata().get(field)
                        for field in (
                            "display_headline",
                            "summary",
                            "why_it_matters",
                            "key_points",
                            "primary_topic",
                            "topic_tags",
                            "event_types",
                            "entity_tags",
                            "maturity",
                        )
                    },
                    "automated_status": after_evaluation.quality_status,
                    "warnings": after_evaluation.warnings,
                    "grounding_overlap": after_evaluation.grounding_overlap,
                    "unsupported_numbers": after_evaluation.unsupported_numbers,
                },
                "human_review": {
                    "faithfulness": "not_reviewed",
                    "coverage": "not_reviewed",
                    "usefulness": "not_reviewed",
                    "headline_quality": "not_reviewed",
                    "taxonomy_accuracy": "not_reviewed",
                    "human_notes": "",
                },
            }
        )

    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prior_payload = {}
    if output.exists():
        try:
            prior_payload = json.loads(output.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            prior_payload = {}
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": 2,
        "generated_at": generated_at,
        "purpose": (
            "Read-only before-and-after regression for sparse-source summary prompt changes."
        ),
        "change_note": arguments.change_note,
        "change_history": [
            *prior_payload.get("change_history", []),
            {
                "generated_at": generated_at,
                "change_note": arguments.change_note,
                "targets": list(TARGETS),
                "database_updated": False,
            },
        ],
        "database_updated": False,
        "prompt_behavior_under_test": [
            "Classify low-detail source text as sparse.",
            "Use near-extractive wording for sparse sources.",
            "Do not infer generic benefits, recommendations, or guaranteed outcomes.",
            "Use neutral affected-scope language for why_it_matters.",
            "Treat configured taxonomy defaults as strong priors.",
        ],
        "targets": list(TARGETS),
        "cases": cases,
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Sparse prompt regression: {output}")
    print(f"Cases generated: {len(cases)}")
    for case in cases:
        print(
            f"{case['source_name']}: "
            f"{case['before']['automated_status']} -> {case['after']['automated_status']}"
        )


if __name__ == "__main__":
    main()
