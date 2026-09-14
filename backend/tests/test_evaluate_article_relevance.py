from scripts.evaluate_article_relevance import evidence_level, summarize


def test_evidence_level_prefers_explicit_state_and_derives_legacy_full_article() -> None:
    assert evidence_level({"evidence_level": "official_feed_excerpt"}) == (
        "official_feed_excerpt"
    )
    assert evidence_level({"extraction_status": "full_article"}) == "full_article"
    assert evidence_level({}) == "source_entry"


def test_summary_separates_default_contextual_and_evidence_eligibility() -> None:
    records = [
        {
            "source": "alpha",
            "relevance_tier": "core",
            "classification_status": "classified",
            "default_rag_eligible": True,
            "contextual_rag_eligible": False,
            "evidence_blocked": False,
        },
        {
            "source": "alpha",
            "relevance_tier": "contextual",
            "classification_status": "classified",
            "default_rag_eligible": False,
            "contextual_rag_eligible": True,
            "evidence_blocked": False,
        },
        {
            "source": "beta",
            "relevance_tier": "core",
            "classification_status": "classified",
            "default_rag_eligible": False,
            "contextual_rag_eligible": False,
            "evidence_blocked": True,
        },
        {
            "source": "beta",
            "relevance_tier": "excluded",
            "classification_status": "classified",
            "default_rag_eligible": False,
            "contextual_rag_eligible": False,
            "evidence_blocked": False,
        },
    ]

    result = summarize(records)

    assert result["evaluated"] == 4
    assert result["tier_counts"] == {"contextual": 1, "core": 2, "excluded": 1}
    assert result["default_rag_eligible"] == 1
    assert result["rag_eligible_with_contextual"] == 2
    assert result["evidence_blocked"] == 1
    assert result["by_source"]["alpha"]["contextual_rag_eligible"] == 1
