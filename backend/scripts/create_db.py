import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

sys.path.append(str(Path(__file__).resolve().parents[1]))

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = BACKEND_DIR / "alembic.ini"


def main() -> None:
    config = Config(str(ALEMBIC_CONFIG))
    command.upgrade(config, "head")
    print("Database schema is at the latest Alembic revision.")


if __name__ == "__main__":
    main()
