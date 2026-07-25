import hashlib
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup


@dataclass(frozen=True)
class FetchedDocument:
    source_name: str
    source_type: str
    url: str
    title: str
    raw_text: str
    content_hash: str


class IngestionService:
    async def fetch_document(
        self,
        source_name: str,
        source_type: str,
        url: str,
    ) -> FetchedDocument:
        title, text = await self.fetch_text(url)
        return FetchedDocument(
            source_name=source_name,
            source_type=source_type,
            url=url,
            title=title,
            raw_text=text,
            content_hash=self.content_hash(text),
        )

    async def fetch_text(self, url: str) -> tuple[str, str]:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            response = await client.get(url)
            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else url

        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.decompose()

        main = soup.find("main") or soup.find("article") or soup.body or soup
        text = "\n".join(line.strip() for line in main.get_text("\n").splitlines() if line.strip())
        return title, text

    def content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
