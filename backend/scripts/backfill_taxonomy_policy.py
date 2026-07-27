import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.source_detail import classify_content_detail, sparse_visibility_metadata
from app.services.taxonomy import infer_maturity, normalize_event_types


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DECISIONS = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "taxonomy_review_decisions_2026-07-26.json"
)
DEFAULT_REPORT = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "taxonomy_backfill_report_2026-07-26.json"
)
POLICY_VERSION = "2026-07-26-v1"


def load_decisions(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload.get("decisions") or {})


def policy_maturity(
    title: str,
    raw_text: str,
    event_types: list[str],
    current: str,
) -> str:
    inferred = infer_maturity(title, raw_text, event_types)
    # Preserve an existing non-stable lifecycle label when the deterministic
    # rules do not find a stronger signal.
    return inferred if inferred != "stable" else (current or "stable")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply reviewed taxonomy corrections and ingestion policy invariants."
    )
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the change report without committing database updates.",
    )
    arguments = parser.parse_args()

    decisions = load_decisions(arguments.decisions.resolve())
    reviewed_ids = set(decisions)
    found_reviewed_ids: set[str] = set()
    field_changes: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    changes: list[dict] = []

    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(Document)
                .where(Document.source_type == "release")
                .order_by(Document.source_name, Document.id)
            )
        )
        for document in documents:
            document_id = str(document.id)
            decision = decisions.get(document_id, {})
            if decision:
                found_reviewed_ids.add(document_id)

            metadata = dict(document.doc_metadata or {})
            before = {
                "primary_topic": metadata.get("primary_topic"),
                "event_types": list(metadata.get("event_types") or []),
                "maturity": metadata.get("maturity"),
            }
            after = dict(before)
            reasons: list[str] = []

            normalized_events = normalize_event_types(
                document.source_name,
                after["event_types"],
            )
            if normalized_events != after["event_types"]:
                after["event_types"] = normalized_events
                reasons.append("source_event_invariant")

            inferred_maturity = policy_maturity(
                str(document.title or ""),
                str(document.raw_text or ""),
                after["event_types"],
                str(after["maturity"] or ""),
            )
            if inferred_maturity != after["maturity"]:
                after["maturity"] = inferred_maturity
                reasons.append("deterministic_maturity")

            if decision.get("primary_topic_review") == "change_required":
                proposed = decision.get("proposed_primary_topic")
                if proposed and proposed != after["primary_topic"]:
                    after["primary_topic"] = proposed
                    reasons.append("reviewed_primary_topic")
            if decision.get("event_types_review") == "change_required":
                proposed = list(decision.get("proposed_event_types") or [])
                if proposed and proposed != after["event_types"]:
                    after["event_types"] = proposed
                    reasons.append("reviewed_event_types")
            if decision.get("maturity_review") == "change_required":
                proposed = decision.get("proposed_maturity")
                if proposed and proposed != after["maturity"]:
                    after["maturity"] = proposed
                    reasons.append("reviewed_maturity")

            for field in before:
                if before[field] != after[field]:
                    field_changes[field] += 1

            content_detail = classify_content_detail(
                str(document.title or ""),
                str(document.raw_text or ""),
            )
            visibility = sparse_visibility_metadata(
                content_detail,
                after["event_types"],
            )
            updated_metadata = {
                **metadata,
                **after,
                **visibility,
                "taxonomy_policy_version": POLICY_VERSION,
            }
            if updated_metadata != metadata:
                document.doc_metadata = updated_metadata

            if before != after:
                for reason in reasons:
                    reason_counts[reason] += 1
                changes.append(
                    {
                        "document_id": document_id,
                        "source_name": document.source_name,
                        "title": document.title,
                        "url": document.canonical_url or document.url,
                        "before": before,
                        "after": after,
                        "reasons": reasons,
                        "review_notes": decision.get("taxonomy_notes"),
                    }
                )

        if arguments.dry_run:
            db.rollback()
        else:
            db.commit()

    missing_reviewed_ids = sorted(reviewed_ids - found_reviewed_ids)
    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if arguments.dry_run else "committed",
        "policy_version": POLICY_VERSION,
        "decisions_file": str(arguments.decisions.resolve()),
        "documents_inspected": len(documents),
        "reviewed_decisions": len(decisions),
        "missing_reviewed_document_ids": missing_reviewed_ids,
        "documents_with_taxonomy_changes": len(changes),
        "field_changes": dict(field_changes),
        "reason_counts": dict(reason_counts),
        "changes": changes,
        "change_history": [
            {
                "date": "2026-07-26",
                "change": (
                    "Applied reviewed change_required decisions, versioned-library "
                    "event invariants, attached-RC maturity parsing, research maturity "
                    "inference, and refreshed sparse visibility."
                ),
                "uncertain_decisions_applied": False,
            }
        ],
    }
    output = arguments.report.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    mode = "Dry run" if arguments.dry_run else "Committed"
    print(f"{mode}: {len(documents)} release documents inspected")
    print(f"Documents with taxonomy changes: {len(changes)}")
    print(f"Field changes: {dict(field_changes)}")
    print(f"Reason counts: {dict(reason_counts)}")
    print(f"Missing reviewed document IDs: {len(missing_reviewed_ids)}")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
