import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.extraction_quality import ExtractionQualityService
from scripts._source_config import update_source_map
from scripts._review_io import review_items_by_key


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "data" / "eval" / "extraction"
HUMAN_LABELS = {
    "not_reviewed",
    "complete",
    "mostly_complete",
    "incomplete",
    "too_much_boilerplate",
    "wrong_content",
}


def load_documents(source: str | None) -> list[Document]:
    stmt = (
        select(Document)
        .options(selectinload(Document.chunks))
        .order_by(Document.source_name, Document.published_at.desc().nullslast(), Document.id)
    )
    if source:
        stmt = stmt.where(Document.source_name == source)
    with SessionLocal() as db:
        return list(db.scalars(stmt).unique())


def existing_reviews(path: Path) -> dict[str, dict]:
    return review_items_by_key(path, "document_id")


def build_review_sample(
    service: ExtractionQualityService,
    evaluations,
    sample_size: int,
    previous: dict[str, dict],
) -> list[dict]:
    sample = service.select_review_sample(evaluations, sample_size)
    items = []
    for evaluation in sample:
        prior = previous.get(evaluation.document_id, {})
        human_label = str(prior.get("human_label") or "not_reviewed")
        if human_label not in HUMAN_LABELS:
            human_label = "not_reviewed"
        items.append(
            {
                "document_id": evaluation.document_id,
                "source_name": evaluation.source_name,
                "title": evaluation.title,
                "url": evaluation.url,
                "automated_status": evaluation.quality_status,
                "warnings": evaluation.warnings,
                "failures": evaluation.failures,
                "human_label": human_label,
                "human_notes": str(prior.get("human_notes") or ""),
            }
        )
    return items


def print_summary(summary: dict) -> None:
    counts = summary["status_counts"]
    print("Extraction evaluation")
    print(f"Documents evaluated: {summary['documents_evaluated']}")
    print(f"Passed: {counts['pass']}")
    print(f"Warnings: {counts['warning']}")
    print(f"Failed: {counts['fail']}")
    if summary["warning_counts"]:
        print("\nWarnings")
        for warning, count in summary["warning_counts"].items():
            print(f"  {warning}: {count}")
    if summary["failure_counts"]:
        print("\nFailures")
        for failure, count in summary["failure_counts"].items():
            print(f"  {failure}: {count}")
    print("\nBy source")
    for source, source_counts in summary["by_source"].items():
        print(
            f"  {source}: pass={source_counts['pass']} "
            f"warning={source_counts['warning']} fail={source_counts['fail']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate stored update extraction quality.")
    parser.add_argument("--source", help="Evaluate one source slug")
    parser.add_argument(
        "--status",
        choices=("pass", "warning", "fail"),
        help="Include only documents with this resulting status",
    )
    parser.add_argument("--sample-size", type=int, default=20, help="Human review sample size")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    arguments = parser.parse_args()

    service = ExtractionQualityService()
    documents = load_documents(arguments.source)
    source_configs = update_source_map()
    evaluations = [
        service.evaluate(
            document,
            document.chunks,
            source_kind=source_configs.get(document.source_name, {}).get("source_kind", "unknown"),
        )
        for document in documents
    ]
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
    report_path = output_dir / "extraction_report.json"
    sample_path = output_dir / "human_review_sample.json"
    summary = service.aggregate(evaluations)
    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "schema_version": 1,
        "generated_at": generated_at,
        "filters": {"source": arguments.source, "status": arguments.status},
        "thresholds": asdict(service.thresholds),
        "summary": summary,
        "documents": [evaluation.as_dict() for evaluation in evaluations],
    }
    review_items = build_review_sample(
        service,
        evaluations,
        max(0, arguments.sample_size),
        existing_reviews(sample_path),
    )
    review = {
        "schema_version": 1,
        "generated_at": generated_at,
        "allowed_human_labels": sorted(HUMAN_LABELS),
        "instructions": (
            "Open url and compare it with the locally stored document, then set human_label "
            "and human_notes. Full source text is intentionally excluded from this public-safe "
            "artifact. "
            "Rerunning the evaluator preserves reviews for documents that remain in the sample."
        ),
        "items": review_items,
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    sample_path.write_text(json.dumps(review, indent=2), encoding="utf-8")

    print_summary(summary)
    print(f"\nReport: {report_path}")
    print(f"Human review sample: {sample_path}")


if __name__ == "__main__":
    main()
