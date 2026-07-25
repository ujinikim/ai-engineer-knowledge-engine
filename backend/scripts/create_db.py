from pathlib import Path
import sys

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import engine


SQL_FILE = Path(__file__).resolve().parents[1] / "sql" / "init.sql"


def main() -> None:
    sql = SQL_FILE.read_text(encoding="utf-8")
    with engine.begin() as connection:
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(text(statement))
    print("Database schema is ready.")


if __name__ == "__main__":
    main()
