import asyncio
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import yaml

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.ingestion import IngestionService


SOURCE_FILE = Path(__file__).resolve().parents[1] / "data" / "sources.yml"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
OUTPUT_FILE = RAW_DIR / "documents.jsonl"


async def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    sources = load_sources()
    ingestion = IngestionService()

    with OUTPUT_FILE.open("w", encoding="utf-8") as output:
        for source in sources:
            for url in source["urls"]:
                try:
                    print(f"Fetching {url}")
                    fetched = await ingestion.fetch_document(
                        source_name=source["source_name"],
                        source_type=source.get("source_type", "docs"),
                        url=url,
                    )
                    row = asdict(fetched) | {
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    }
                    output.write(json.dumps(row, ensure_ascii=False) + "\n")
                    print(f"Collected {fetched.title}: {len(fetched.raw_text)} chars")
                except Exception as error:
                    print(f"Failed {url}: {error}")

    print(f"Raw collection written to {OUTPUT_FILE}")


def load_sources() -> list[dict]:
    with SOURCE_FILE.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data["sources"]


if __name__ == "__main__":
    asyncio.run(main())
