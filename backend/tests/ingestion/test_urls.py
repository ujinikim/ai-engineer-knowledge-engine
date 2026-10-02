from app.ingestion.urls import normalize_url, url_candidates


def test_document_urls_normalize_trailing_slashes_without_losing_fragments():

    assert (
        normalize_url("https://example.com/releases/item/#details")
        == "https://example.com/releases/item#details"
    )
    assert url_candidates(
        "https://example.com/releases/item/"
    ) == [
        "https://example.com/releases/item",
        "https://example.com/releases/item/",
    ]


def test_document_urls_normalize_hosts_queries_and_tracking_parameters():

    assert normalize_url(
        "HTTPS://Example.COM:443/article/?b=2&utm_source=email&a=1#section"
    ) == "https://example.com/article?a=1&b=2#section"
