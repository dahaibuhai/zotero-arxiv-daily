from datetime import date, timedelta
import time

import requests
from loguru import logger

from providers.common import ExternalPaper


BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
MAX_RETRIES = 5
BASE_RETRY_SECONDS = 5.0
REQUEST_INTERVAL_SECONDS = 3.0


def parse_queries(raw: str) -> list[str]:
    return [line.strip() for line in (raw or "").splitlines() if line.strip()]


def request_with_retry(params: dict, headers: dict) -> requests.Response:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                BASE_URL,
                params=params,
                headers=headers,
                timeout=30,
            )
        except requests.RequestException as exc:
            if attempt >= MAX_RETRIES:
                raise
            delay = min(60.0, BASE_RETRY_SECONDS * (2 ** (attempt - 1)))
            logger.warning(
                "Semantic Scholar request failed (attempt {}/{}): {}. "
                "Retrying in {:.0f}s.",
                attempt,
                MAX_RETRIES,
                exc,
                delay,
            )
            time.sleep(delay)
            continue

        if response.status_code in (401, 403) and headers.pop("x-api-key", None):
            logger.warning(
                "Semantic Scholar rejected the configured API key. "
                "Retrying anonymously."
            )
            continue

        if response.status_code == 429 or response.status_code >= 500:
            if attempt >= MAX_RETRIES:
                response.raise_for_status()

            retry_after = response.headers.get("Retry-After")
            try:
                delay = float(retry_after) if retry_after else 0.0
            except ValueError:
                delay = 0.0
            if delay <= 0:
                delay = BASE_RETRY_SECONDS * (2 ** (attempt - 1))
            delay = min(120.0, max(1.0, delay))

            logger.warning(
                "Semantic Scholar returned HTTP {} (attempt {}/{}). "
                "Retrying in {:.0f}s.",
                response.status_code,
                attempt,
                MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
            continue

        response.raise_for_status()
        return response

    raise RuntimeError("Semantic Scholar request failed after retries.")


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

    if headers:
        logger.info("Using authenticated Semantic Scholar access.")
    else:
        logger.info("Using anonymous Semantic Scholar access.")

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
        response = request_with_retry(params=params, headers=headers)
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

            authors = [
                author.get("name", "")
                for author in item.get("authors", [])
                if author.get("name")
            ]
            external_ids = item.get("externalIds") or {}
            open_pdf = item.get("openAccessPdf") or {}
            pdf_url = open_pdf.get("url") or item.get("url") or ""
            paper_id = (
                external_ids.get("ArXiv")
                or external_ids.get("DOI")
                or item.get("paperId")
                or ""
            )

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

        time.sleep(REQUEST_INTERVAL_SECONDS)

    return papers
