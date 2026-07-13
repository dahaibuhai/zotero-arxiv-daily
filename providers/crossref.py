from datetime import date, timedelta
from html import unescape
import re
import time

from loguru import logger
import requests

from providers.common import ExternalPaper


BASE_URL = "https://api.crossref.org/journals/{issn}/works"
MAX_RETRIES = 3


def parse_journals(raw: str) -> list[tuple[str, str, float]]:
    journals = []
    for line_number, line in enumerate((raw or "").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) != 3:
            raise ValueError(
                f"Invalid CROSSREF_JOURNALS line {line_number}: {line!r}. "
                "Expected: journal name|ISSN|weight"
            )
        name, issn, weight = parts
        journals.append((name, issn, float(weight)))
    return journals


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(value)).strip()


def get_publication_date(item: dict) -> str:
    for field in ("published-online", "published-print", "published", "issued"):
        date_parts = (item.get(field) or {}).get("date-parts") or []
        if date_parts and date_parts[0]:
            parts = list(date_parts[0]) + [1, 1]
            try:
                return date(*parts[:3]).isoformat()
            except (TypeError, ValueError):
                continue
    return ""


def request_items(issn: str, params: dict, headers: dict) -> list[dict]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                BASE_URL.format(issn=issn),
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("items", [])
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise
            delay = min(30, 5 * (2 ** (attempt - 1)))
            logger.warning(
                "Crossref request for ISSN {} failed (attempt {}/{}): {}. "
                "Retrying in {}s.",
                issn,
                attempt,
                MAX_RETRIES,
                exc,
                delay,
            )
            time.sleep(delay)
    return []


def fetch_crossref_papers(
    journals_raw: str,
    days: int = 7,
    rows: int = 5,
    mailto: str = "",
) -> list[ExternalPaper]:
    start_date = date.today() - timedelta(days=max(1, days))
    rows = max(1, min(rows, 100))
    papers = []
    headers = {
        "User-Agent": (
            f"zotero-arxiv-daily/1.0 (mailto:{mailto})"
            if mailto
            else "zotero-arxiv-daily/1.0"
        )
    }

    for journal_name, issn, journal_weight in parse_journals(journals_raw):
        params = {
            "filter": f"from-pub-date:{start_date.isoformat()},type:journal-article",
            "sort": "published",
            "order": "desc",
            "rows": rows,
        }
        if mailto:
            params["mailto"] = mailto

        try:
            items = request_items(issn, params, headers)
        except requests.RequestException as exc:
            logger.warning(
                "Skipping Crossref journal {} ({}) after repeated failure: {}",
                journal_name,
                issn,
                exc,
            )
            continue

        for item in items:
            title = clean_text(" ".join(item.get("title") or []))
            if not title:
                continue

            abstract = clean_text(item.get("abstract") or "")
            doi = (item.get("DOI") or "").strip()
            landing_url = f"https://doi.org/{doi}" if doi else (item.get("URL") or "")
            authors = []
            for author in item.get("author", []):
                name = " ".join(
                    [author.get("given", ""), author.get("family", "")]
                ).strip()
                if name:
                    authors.append(name)

            papers.append(
                ExternalPaper(
                    title=title,
                    summary=abstract or title,
                    authors=authors,
                    paper_id=doi or title,
                    pdf_url=landing_url,
                    source="Crossref",
                    venue=journal_name,
                    publication_date=get_publication_date(item),
                    doi=doi,
                    journal_weight=journal_weight,
                    link_label="DOI",
                )
            )

        time.sleep(1.0)

    return papers
