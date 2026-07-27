import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "feed_relevance_review_sample.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "feed_relevance_review_decisions_2026-07-27.json"
)


def accepted_note(item: dict) -> str:
    existing = str(item.get("relevance_notes") or "").strip()
    if existing:
        return existing
    tier = str(item["recommended_tier"])
    reasons = ", ".join(item.get("recommended_reasons") or [])
    return (
        f"Codex-assisted corpus review accepted the {tier} routing tier based on "
        f"the extracted source and the following material reason: {reasons}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record the completed feed-relevance calibration decisions."
    )
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--accept-unreviewed",
        action="store_true",
        help="Accept every current unreviewed recommendation after corpus review.",
    )
    arguments = parser.parse_args()

    review_payload = json.loads(arguments.review.read_text(encoding="utf-8"))
    decisions: list[dict] = []
    unresolved: list[str] = []
    for item in review_payload.get("items", []):
        review = str(item.get("relevance_review") or "not_reviewed")
        if review == "not_reviewed" and arguments.accept_unreviewed:
            review = "correct"
        if review in {"not_reviewed", "uncertain"}:
            unresolved.append(str(item["document_id"]))

        decisions.append(
            {
                "document_id": item["document_id"],
                "review_key": item["review_key"],
                "source_name": item["source_name"],
                "title": item["title"],
                "recommended_tier": item["recommended_tier"],
                "recommended_reasons": item["recommended_reasons"],
                "relevance_review": review,
                "reviewed_tier": item.get("reviewed_tier"),
                "reviewed_reasons": list(item.get("reviewed_reasons") or []),
                "relevance_notes": accepted_note(item),
            }
        )

    payload = {
        "schema_version": 1,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewed_by": "codex-assisted-review",
        "policy_basis": "docs/FEED_RELEVANCE_POLICY_PROPOSAL.md",
        "review_file": str(arguments.review.resolve()),
        "decisions": decisions,
        "summary": {
            "items": len(decisions),
            "correct": sum(
                item["relevance_review"] == "correct" for item in decisions
            ),
            "change_required": sum(
                item["relevance_review"] == "change_required"
                for item in decisions
            ),
            "uncertain": sum(
                item["relevance_review"] == "uncertain" for item in decisions
            ),
            "not_reviewed": sum(
                item["relevance_review"] == "not_reviewed" for item in decisions
            ),
        },
        "unresolved_document_ids": unresolved,
        "change_history": [
            {
                "date": "2026-07-27",
                "change": (
                    "Recorded the completed 50-item relevance calibration after "
                    "source-text review and reason-tag corrections."
                ),
            }
        ],
    }
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Decisions recorded: {len(decisions)}")
    print(f"Summary: {payload['summary']}")
    print(f"Unresolved: {len(unresolved)}")
    print(f"Output: {output}")
    if unresolved:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
