import json
from pathlib import Path


EVAL_ROOT = Path(__file__).resolve().parents[1] / "data" / "eval"
PRIVATE_SOURCE_FIELDS = {"source_text", "extracted_text"}


def private_source_paths(value: object, path: tuple[object, ...] = ()) -> list[str]:
    matches: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = (*path, key)
            if key in PRIVATE_SOURCE_FIELDS:
                matches.append(".".join(str(part) for part in child_path))
            matches.extend(private_source_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            matches.extend(private_source_paths(child, (*path, index)))
    return matches


def test_tracked_evaluation_artifacts_exclude_full_source_text() -> None:
    violations: list[str] = []
    for artifact in sorted(EVAL_ROOT.rglob("*.json")):
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        for field_path in private_source_paths(payload):
            violations.append(f"{artifact.relative_to(EVAL_ROOT)}:{field_path}")

    assert not violations, (
        "Public evaluation artifacts must not contain full source text. "
        f"Remove these fields: {violations}"
    )
