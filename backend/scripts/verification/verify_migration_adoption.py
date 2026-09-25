import argparse
from pathlib import Path
import sys

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.session import engine


SENTINEL_ID = "00000000-0000-0000-0000-000000000001"


def seed() -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO documents (id, source_name, title, url, raw_text, content_hash)
                VALUES (
                    :id,
                    'migration-test',
                    'Preserve me',
                    'https://example.com/migration-test',
                    'sentinel',
                    'sentinel'
                )
                """
            ),
            {"id": SENTINEL_ID},
        )


def verify() -> None:
    with engine.connect() as connection:
        preserved = connection.scalar(
            text("SELECT count(*) FROM documents WHERE id = :id"),
            {"id": SENTINEL_ID},
        )

    if preserved != 1:
        raise RuntimeError("The legacy-schema adoption test did not preserve its sentinel row.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed or verify the disposable legacy-schema adoption test."
    )
    parser.add_argument("action", choices=("seed", "verify"))
    args = parser.parse_args()

    if args.action == "seed":
        seed()
    else:
        verify()


if __name__ == "__main__":
    main()
