import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE = (
    ROOT / "data" / "eval" / "summaries" / "taxonomy_review_sample.json"
)
DEFAULT_DECISIONS = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "taxonomy_review_decisions_2026-07-26.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "taxonomy_regression_report_2026-07-26.json"
)
AXES = {
    "primary_topic": ("primary_topic_review", "proposed_primary_topic"),
    "event_types": ("event_types_review", "proposed_event_types"),
    "maturity": ("maturity_review", "proposed_maturity"),
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate stored taxonomy against the completed human review."
    )
    parser.add_argument("--sample", type=Path, default=DEFAULT_SAMPLE)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    sample_payload = json.loads(arguments.sample.read_text(encoding="utf-8"))
    decisions_payload = json.loads(arguments.decisions.read_text(encoding="utf-8"))
    decisions = dict(decisions_payload.get("decisions") or {})

    with SessionLocal() as db:
        documents = {
            str(document.id): document
            for document in db.scalars(
                select(Document).where(Document.source_type == "release")
            )
        }

    counts: Counter[str] = Counter()
    results: list[dict] = []
    for item in sample_payload.get("items", []):
        document_id = str(item["document_id"])
        document = documents.get(document_id)
        decision = decisions.get(document_id)
        if not document or not decision:
            results.append(
                {
                    "document_id": document_id,
                    "title": item.get("title"),
                    "status": "missing",
                    "missing_document": document is None,
                    "missing_decision": decision is None,
                }
            )
            counts["missing"] += 1
            continue

        metadata = dict(document.doc_metadata or {})
        baseline = dict(item.get("generated_taxonomy") or {})
        axis_results: dict[str, dict] = {}
        item_passed = True
        for field, (review_field, proposed_field) in AXES.items():
            review = str(decision.get(review_field) or "not_reviewed")
            expected = (
                decision.get(proposed_field)
                if review == "change_required"
                else baseline.get(field)
            )
            if field == "event_types":
                expected = list(expected or [])
                actual = list(metadata.get(field) or [])
            else:
                actual = metadata.get(field)
            passed = actual == expected
            item_passed = item_passed and passed
            counts[f"{review}_axes"] += 1
            counts[f"{review}_{'passed' if passed else 'failed'}"] += 1
            axis_results[field] = {
                "review": review,
                "expected": expected,
                "actual": actual,
                "passed": passed,
            }

        results.append(
            {
                "document_id": document_id,
                "source_name": document.source_name,
                "title": document.title,
                "status": "passed" if item_passed else "failed",
                "axes": axis_results,
            }
        )
        counts["items_passed" if item_passed else "items_failed"] += 1

    failures = [result for result in results if result["status"] != "passed"]
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "taxonomy_policy_version": "2026-07-26-v1",
        "sample_file": str(arguments.sample.resolve()),
        "decisions_file": str(arguments.decisions.resolve()),
        "reviewed_items": len(sample_payload.get("items", [])),
        "reviewed_axes": len(sample_payload.get("items", [])) * len(AXES),
        "passed": not failures,
        "counts": dict(counts),
        "failures": failures,
        "results": results,
        "change_history": [
            {
                "date": "2026-07-26",
                "change": (
                    "Validated post-backfill stored taxonomy against all correct, "
                    "change_required, and uncertain human-review decisions."
                ),
            }
        ],
    }
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Reviewed items: {report['reviewed_items']}")
    print(f"Reviewed axes: {report['reviewed_axes']}")
    print(f"Items passed: {counts['items_passed']}")
    print(f"Items failed or missing: {len(failures)}")
    print(f"Report: {output}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
