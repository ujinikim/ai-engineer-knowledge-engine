import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.summary_quality import SummaryQualityService
from scripts._review_io import read_review_payload, review_items_by_key


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "eval" / "summaries"
HUMAN_RATINGS = {
    "faithfulness": {"not_reviewed", "faithful", "minor_issue", "major_issue"},
    "coverage": {"not_reviewed", "complete", "partial", "misses_main_point"},
    "usefulness": {"not_reviewed", "useful", "somewhat_useful", "not_useful"},
    "headline_quality": {"not_reviewed", "good", "acceptable", "poor"},
    "taxonomy_accuracy": {"not_reviewed", "correct", "partial", "incorrect"},
}


def load_documents(source: str | None) -> list[Document]:
    stmt = (
        select(Document)
        .order_by(Document.source_name, Document.published_at.desc().nullslast(), Document.id)
    )
    if source:
        stmt = stmt.where(Document.source_name == source)
    with SessionLocal() as db:
        return list(db.scalars(stmt))


def existing_reviews(path: Path) -> dict[str, dict]:
    return review_items_by_key(path, "review_key")


def existing_review_payload(path: Path) -> dict:
    return read_review_payload(path)


def preserved_rating(prior: dict, field: str) -> str:
    value = str(prior.get(field) or "not_reviewed")
    return value if value in HUMAN_RATINGS[field] else "not_reviewed"


def build_review_sample(
    service: SummaryQualityService,
    evaluations,
    sample_size: int,
    previous: dict[str, dict],
) -> list[dict]:
    items = []
    for evaluation in service.select_review_sample(evaluations, sample_size):
        prior = previous.get(evaluation.review_key, {})
        items.append(
            {
                "document_id": evaluation.document_id,
                "review_key": evaluation.review_key,
                "source_name": evaluation.source_name,
                "source_type": evaluation.source_type,
                "title": evaluation.title,
                "url": evaluation.url,
                "generated_by": evaluation.generated_by,
                "automated_status": evaluation.quality_status,
                "warnings": evaluation.warnings,
                "generated_summary": {
                    "display_headline": evaluation.display_headline,
                    "summary": evaluation.summary,
                    "why_it_matters": evaluation.why_it_matters,
                    "key_points": evaluation.key_points,
                    "primary_topic": evaluation.primary_topic,
                    "event_types": evaluation.event_types,
                },
                "automated_metrics": {
                    "headline_characters": evaluation.headline_characters,
                    "summary_word_count": evaluation.summary_word_count,
                    "why_it_matters_word_count": evaluation.why_it_matters_word_count,
                    "key_point_count": evaluation.key_point_count,
                    "grounding_overlap": evaluation.grounding_overlap,
                    "unsupported_numbers": evaluation.unsupported_numbers,
                },
                "faithfulness": preserved_rating(prior, "faithfulness"),
                "coverage": preserved_rating(prior, "coverage"),
                "usefulness": preserved_rating(prior, "usefulness"),
                "headline_quality": preserved_rating(prior, "headline_quality"),
                "taxonomy_accuracy": preserved_rating(prior, "taxonomy_accuracy"),
                "human_notes": str(prior.get("human_notes") or ""),
            }
        )
    return items


def print_summary(summary: dict) -> None:
    counts = summary["status_counts"]
    print("Summary evaluation")
    print(f"Documents evaluated: {summary['documents_evaluated']}")
    print(f"Passed: {counts['pass']}")
    print(f"Warnings: {counts['warning']}")
    print(f"Failed: {counts['fail']}")
    print(f"Average lexical grounding: {summary['average_grounding_overlap']:.4f}")
    if summary["warning_counts"]:
        print("\nWarnings")
        for warning, count in summary["warning_counts"].items():
            print(f"  {warning}: {count}")
    if summary["failure_counts"]:
        print("\nFailures")
        for failure, count in summary["failure_counts"].items():
            print(f"  {failure}: {count}")
    print("\nBy source type")
    for source_type, source_counts in summary["by_source_type"].items():
        print(
            f"  {source_type}: pass={source_counts['pass']} "
            f"warning={source_counts['warning']} fail={source_counts['fail']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate stored article summaries.")
    parser.add_argument("--source", help="Evaluate one source slug")
    parser.add_argument(
        "--status",
        choices=("pass", "warning", "fail"),
        help="Include only documents with this resulting status",
    )
    parser.add_argument("--sample-size", type=int, default=10, help="Human review sample size")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--change-note",
        help="Describe what changed since the prior human-review artifact.",
    )
    arguments = parser.parse_args()

    service = SummaryQualityService()
    documents = load_documents(arguments.source)
    evaluations = [service.evaluate(document) for document in documents]
    if arguments.status:
        evaluations = [
            evaluation
            for evaluation in evaluations
            if evaluation.quality_status == arguments.status
        ]
        included_ids = {evaluation.document_id for evaluation in evaluations}
        documents = [document for document in documents if str(document.id) in included_ids]

    output_dir = arguments.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "summary_report.json"
    sample_path = output_dir / "human_review_sample.json"
    prior_review_payload = existing_review_payload(sample_path)
    generated_at = datetime.now(timezone.utc).isoformat()
    summary = service.aggregate(evaluations)
    report = {
        "schema_version": 1,
        "generated_at": generated_at,
        "filters": {"source": arguments.source, "status": arguments.status},
        "thresholds": asdict(service.thresholds),
        "summary": summary,
        "documents": [evaluation.as_dict() for evaluation in evaluations],
    }
    review = {
        "schema_version": 2,
        "generated_at": generated_at,
        "purpose": "Phase 2 human calibration of generated article summaries and taxonomy.",
        "change_history": [
            *prior_review_payload.get("change_history", []),
            {
                "generated_at": generated_at,
                "change_note": arguments.change_note
                or "Evaluation regenerated; no additional change description was supplied.",
                "documents_evaluated": summary["documents_evaluated"],
                "sample_size": max(0, arguments.sample_size),
                "filters": {"source": arguments.source, "status": arguments.status},
            },
        ],
        "allowed_ratings": {
            field: sorted(values) for field, values in HUMAN_RATINGS.items()
        },
        "instructions": (
            "Open url or use the locally stored document and compare it with generated_summary. "
            "Rate faithfulness, coverage, usefulness, headline_quality, and taxonomy_accuracy "
            "using allowed_ratings. Add concise evidence to human_notes. Full source text is "
            "intentionally excluded from this public-safe artifact. Ratings are preserved only "
            "when review_key is unchanged."
        ),
        "items": build_review_sample(
            service,
            evaluations,
            max(0, arguments.sample_size),
            existing_reviews(sample_path),
        ),
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    sample_path.write_text(json.dumps(review, indent=2), encoding="utf-8")

    print_summary(summary)
    print(f"\nReport: {report_path}")
    print(f"Human review sample: {sample_path}")


if __name__ == "__main__":
    main()
