"""Canonical article URLs, so a re-collected article matches its stored row."""

from urllib.parse import parse_qsl, urlencode, urlparse

TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_url(value: str) -> str:
    """Lowercase scheme and host, drop default ports, trailing slashes, and tracking parameters."""
    parsed = urlparse(value.strip())
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        hostname = f"{hostname}:{port}"
    path = parsed.path
    if path and path != "/":
        path = path.rstrip("/")
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parsed.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
        ),
        doseq=True,
    )
    return parsed._replace(scheme=scheme, netloc=hostname, path=path, query=query).geturl()


def url_candidates(value: str) -> list[str]:
    """The normalized URL plus its trailing-slash form, as older rows may store it."""
    normalized = normalize_url(value)
    parsed = urlparse(normalized)
    candidates = [normalized]
    if parsed.path and parsed.path != "/":
        candidates.append(parsed._replace(path=f"{parsed.path}/").geturl())
    return list(dict.fromkeys(candidates))
