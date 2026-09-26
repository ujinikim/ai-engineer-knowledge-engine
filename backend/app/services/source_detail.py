import re


SPARSE_BODY_WORDS = 50
SPARSE_SUBSTANTIVE_SENTENCES = 2
IMPORTANT_SPARSE_EVENT_TYPES = frozenset(
    {
        "alert",
        "security-issue",
        "breaking-change",
        "deprecation",
        "incident",
    }
)


def classify_content_detail(title: str, raw_text: str) -> str:
    body = raw_text.removeprefix(title).strip()
    words = re.findall(r"\b[\w+#.-]+\b", body)
    substantive_sentences = [
        sentence
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", body)
        if len(re.findall(r"\b[\w+#.-]+\b", sentence)) >= 6
    ]
    if (
        len(words) < SPARSE_BODY_WORDS
        or len(substantive_sentences) < SPARSE_SUBSTANTIVE_SENTENCES
    ):
        return "sparse"
    return "detailed"
