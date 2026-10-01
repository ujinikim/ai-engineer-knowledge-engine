from app.ingestion.content_detail import classify_content_detail


def test_content_detail_classifies_sparse_and_detailed_sources() -> None:
    sparse_title = "v1.2.3"
    sparse_text = f"{sparse_title}\n\nFix query errors when using shard keys while resharding."
    detailed_body = " ".join(
        [
            "The release introduces a cache for production inference workloads.",
            "Production testing reduced median latency across three representative deployments.",
            "Operators can enable the cache through the existing runtime configuration.",
            "Compatibility details cover existing deployments and supported runtime versions.",
            "The release notes provide benchmark methodology and staged rollout guidance.",
            "Additional examples explain monitoring behavior during the migration process.",
        ]
    )
    detailed_title = "Cache release"

    assert classify_content_detail(sparse_title, sparse_text) == "sparse"
    assert classify_content_detail(detailed_title, f"{detailed_title}\n\n{detailed_body}") == "detailed"
