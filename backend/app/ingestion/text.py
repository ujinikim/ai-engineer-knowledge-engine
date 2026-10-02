"""Normalize and shorten model-generated text."""


def shorten_at_word_boundary(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    available = limit - 3
    candidate = value[:available].rstrip()
    if " " in candidate:
        word_boundary = candidate.rfind(" ")
        if word_boundary >= max(available // 2, 1):
            candidate = candidate[:word_boundary].rstrip()
    return candidate + "..."


def clean_text(value: object, fallback: str, limit: int) -> str:
    """Collapse whitespace and shorten; an empty value takes the fallback."""
    text = " ".join(str(value or "").split())
    return shorten_at_word_boundary(text, limit) if text else fallback


def clean_text_list(value: object, fallback: list[str], count: int, limit: int) -> list[str]:
    if not isinstance(value, list):
        return fallback
    items = [
        shorten_at_word_boundary(" ".join(str(item).split()), limit)
        for item in value
        if str(item).strip()
    ]
    return items[:count] or fallback
