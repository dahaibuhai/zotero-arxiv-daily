from datetime import date, timedelta
import time

import requests
from loguru import logger

from providers.common import ExternalPaper


BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
MAX_RETRIES = 5
BASE_RETRY_SECONDS = 5.0
REQUEST_INTERVAL_SECONDS = 3.0

PAPER_FIELDS = ",".join(
    [
        "title",
        "abstract",
        "url",
        "authors",
        "venue",
        "journal",
        "year",
        "publicationDate",
        "externalIds",
        "openAccessPdf",
        "citationCount",
        "influentialCitationCount",
    ]
)


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


def paper_from_item(item: dict, *, is_classic_fallback: bool = False) -> ExternalPaper | None:
    title = item.get("title") or ""
    if not title:
        return None

    authors = [
        author.get("name", "")
        for author in item.get("authors", [])
        if author.get("name")
    ]
    external_ids = item.get("externalIds") or {}
    journal = item.get("journal") or {}
    open_pdf = item.get("openAccessPdf") or {}
    pdf_url = open_pdf.get("url") or item.get("url") or ""
    paper_id = (
        external_ids.get("ArXiv")
        or external_ids.get("DOI")
        or item.get("paperId")
        or ""
    )

    return ExternalPaper(
        title=title,
        summary=item.get("abstract") or title,
        authors=authors,
        paper_id=paper_id,
        pdf_url=pdf_url,
        source="Semantic Scholar",
        venue=item.get("venue") or journal.get("name") or "",
        publication_date=item.get("publicationDate") or "",
        doi=external_ids.get("DOI") or "",
        citation_count=item.get("citationCount") or 0,
        influential_citation_count=item.get("influentialCitationCount") or 0,
        is_classic_fallback=is_classic_fallback,
    )


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
    for query in queries:
        params = {
            "query": query,
            "fields": PAPER_FIELDS,
            "publicationDateOrYear": f"{start_date.isoformat()}:",
            "sort": "publicationDate:desc",
        }
        try:
            response = request_with_retry(params=params, headers=headers)
            data = response.json().get("data", [])
        except requests.RequestException as exc:
            # Semantic Scholar is an optional discovery source.  A persistent
            # rate limit or transient network error for one query must not
            # prevent arXiv/Crossref results from being sent.
            logger.warning(
                "Skipping Semantic Scholar query after retries: {!r} ({})",
                query,
                exc,
            )
            continue
        except ValueError as exc:
            logger.warning(
                "Skipping Semantic Scholar query with an invalid response: {!r} ({})",
                query,
                exc,
            )
            continue

        kept = 0
        for item in data:
            paper = paper_from_item(item)
            if paper is None:
                continue

            publication_date = paper.publication_date
            if publication_date:
                try:
                    if date.fromisoformat(publication_date) < start_date:
                        continue
                except ValueError:
                    pass

            papers.append(paper)
            kept += 1
            if kept >= max_results_per_query:
                break

        time.sleep(REQUEST_INTERVAL_SECONDS)

    return papers


def fetch_classic_semantic_scholar_papers(
    queries_raw: str,
    api_key: str | None = None,
    recent_days: int = 14,
    max_results_per_query: int = 20,
    min_citations: int = 20,
):
    """Fetch older, highly cited candidates for an empty daily S2 result set."""
    queries = parse_queries(queries_raw)
    if not queries:
        logger.info("No Semantic Scholar queries configured for classic fallback.")
        return []

    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    classic_cutoff = date.today() - timedelta(days=max(recent_days, 0) + 1)
    papers = []
    for query in queries:
        params = {
            "query": query,
            "fields": PAPER_FIELDS,
            "publicationDateOrYear": f":{classic_cutoff.isoformat()}",
            "minCitationCount": str(max(min_citations, 0)),
            "sort": "citationCount:desc",
        }
        try:
            response = request_with_retry(params=params, headers=headers)
            data = response.json().get("data", [])
        except requests.RequestException as exc:
            logger.warning(
                "Skipping Semantic Scholar classic query after retries: {!r} ({})",
                query,
                exc,
            )
            continue
        except ValueError as exc:
            logger.warning(
                "Skipping Semantic Scholar classic query with an invalid response: {!r} ({})",
                query,
                exc,
            )
            continue

        kept = 0
        for item in data:
            paper = paper_from_item(item, is_classic_fallback=True)
            if paper is None:
                continue
            papers.append(paper)
            kept += 1
            if kept >= max_results_per_query:
                break

        time.sleep(REQUEST_INTERVAL_SECONDS)

    return papers
