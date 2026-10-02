import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_the_api_process_does_not_load_ingestion_code() -> None:
    """Serving, the database layer, and the API depend on `app.domain`, never on ingestion."""
    script = (
        "import sys, app.main\n"
        "loaded = [m for m in sys.modules if m.startswith('app.ingestion')]\n"
        "heavy = [m for m in ('feedparser', 'bs4') if m in sys.modules]\n"
        "print(loaded, heavy)\n"
        "raise SystemExit(1 if loaded or heavy else 0)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, cwd=BACKEND_DIR
    )

    assert result.returncode == 0, f"API imported ingestion code: {result.stdout.strip()} {result.stderr[-300:]}"
