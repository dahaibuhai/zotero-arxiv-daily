from datetime import date, timedelta
import time

import requests
from loguru import logger

from providers.common import ExternalPaper


BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"


def parse_queries(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def fetch_semantic_scholar_papers(
    queries_raw: str,
    api_key: str | None = None,
    days: int = 14,
    max_results_per_query: int = 20,
):
    queries = parse_queries(queries_raw)
    if not queries:
        logger.info("No Semantic Scholar queries configured.")
        return []

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    start_date = date.today() - timedelta(days=days)
    papers = []
    fields = ",".join(
        [
            "title",
            "abstract",
            "url",
            "authors",
            "venue",
            "year",
            "publicationDate",
            "externalIds",
            "openAccessPdf",
        ]
    )

    for query in queries:
        params = {
            "query": query,
            "fields": fields,
            "year": f"{start_date.year}-",
            "sort": "publicationDate:desc",
        }
        response = requests.get(BASE_URL, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json().get("data", [])

        kept = 0
        for item in data:
            title = item.get("title") or ""
            if not title:
                continue

            publication_date = item.get("publicationDate") or ""
            if publication_date:
                try:
                    if date.fromisoformat(publication_date) < start_date:
                        continue
                except ValueError:
                    pass

            authors = [author.get("name", "") for author in item.get("authors", []) if author.get("name")]
            external_ids = item.get("externalIds") or {}
            open_pdf = item.get("openAccessPdf") or {}
            pdf_url = open_pdf.get("url") or item.get("url") or ""
            paper_id = external_ids.get("ArXiv") or external_ids.get("DOI") or item.get("paperId") or ""

            papers.append(
                ExternalPaper(
                    title=title,
                    summary=item.get("abstract") or title,
                    authors=authors,
                    paper_id=paper_id,
                    pdf_url=pdf_url,
                    source="Semantic Scholar",
                    venue=item.get("venue") or "",
                    publication_date=publication_date,
                    doi=external_ids.get("DOI") or "",
                )
            )
            kept += 1
            if kept >= max_results_per_query:
                break

        time.sleep(1.1)

    return papers
