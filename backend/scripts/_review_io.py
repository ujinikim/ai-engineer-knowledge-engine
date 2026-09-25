"""Read prior human-review decisions without overwriting them on reruns."""

import json
from pathlib import Path


def read_review_payload(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def review_items_by_key(path: Path, key: str) -> dict[str, dict]:
    return {
        str(item[key]): item
        for item in read_review_payload(path).get("items", [])
        if isinstance(item, dict) and item.get(key)
    }
