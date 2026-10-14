"""Bounded topic/date search through arXiv's documented Atom API."""

import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

API_URL = "https://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom",
      "o": "http://a9.com/-/spec/opensearch/1.1/"}
TOPIC_SEARCHES = {
    "core": '(all:sputtering OR all:sputtered OR all:"hollow cathode" OR all:HiPIMS)',
    "films": '(all:"thin film" OR all:coating OR all:epitaxy OR all:"epitaxial growth" OR all:"atomic layer deposition" OR all:"chemical vapor deposition" OR all:"pulsed laser deposition" OR all:"molecular beam epitaxy" OR ((all:ALD OR all:CVD OR all:PLD OR all:PVD OR all:MBE) AND (all:film OR all:deposition OR all:growth)))',
    "plasma": '(all:"glow discharge" OR all:"low pressure plasma" OR all:"plasma diagnostics" OR all:"plasma sheath" OR all:"plasma reactor" OR all:"plasma etching" OR all:"plasma surface treatment" OR all:"radio frequency plasma")',
}
_last_request_at = 0.0


def build_query(topic, start, end):
    return f'{TOPIC_SEARCHES[topic]} AND submittedDate:[{start:%Y%m%d%H%M} TO {end:%Y%m%d%H%M}]'


def request_feed(url):
    global _last_request_at
    for attempt in range(3):
        time.sleep(max(0.0, 3.0 - (time.monotonic() - _last_request_at)))
        _last_request_at = time.monotonic()
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "zotero-arxiv-daily/0.3.5 (literature digest)"})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(3 * (2 ** attempt))


def parse_feed(data, start, end, paper_factory=None):
    if paper_factory is None:
        from providers.common import ExternalPaper
        paper_factory = ExternalPaper
    root = ET.fromstring(data)
    total = int(root.findtext("o:totalResults", "0", NS))
    entries = root.findall("a:entry", NS)
    papers = []
    for entry in entries:
        identifier = entry.findtext("a:id", "", NS)
        if "/api/errors" in identifier:
            raise ValueError(entry.findtext("a:summary", "arXiv API error", NS))
        published = entry.findtext("a:published", "", NS)
        timestamp = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if not start <= timestamp <= end:
            continue
        arxiv_id = re.sub(r"v\d+$", "", identifier.rsplit("/abs/", 1)[-1])
        if not re.fullmatch(r"\d{4}\.\d{4,5}|[a-z.-]+/\d{7}", arxiv_id):
            raise ValueError("Unexpected arXiv identifier: " + identifier)
        papers.append(paper_factory(
            title=" ".join(entry.findtext("a:title", "", NS).split()),
            summary=entry.findtext("a:summary", "", NS).strip(),
            authors=[author.findtext("a:name", "", NS) for author in entry.findall("a:author", NS)],
            paper_id=arxiv_id, doi=entry.findtext("x:doi", "", NS),
            pdf_url="https://arxiv.org/pdf/" + arxiv_id,
            publication_date=published, source="arXiv", venue="arXiv"))
    return papers, total, len(entries)


def fetch_recent_arxiv_papers(*, days=7, skip_days=0, now=None, max_results_per_topic=200,
                             fetch_feed=None, paper_factory=None, on_error=None):
    if not 0 <= skip_days < days <= 14 or max_results_per_topic <= 0:
        raise ValueError("arXiv backfill requires 0 <= skip_days < days <= 14 and a positive budget.")
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).replace(second=0, microsecond=0)
    start = now - timedelta(days=days)
    end = now - timedelta(days=skip_days)
    # Inclusive boundaries overlap at exactly seven days; identity deduplication
    # handles the overlap without leaving a minute-wide gap in coverage.
    candidates = []
    fetch_feed = fetch_feed or request_feed
    for topic in TOPIC_SEARCHES:
        offset = 0
        try:
            while offset < max_results_per_topic:
                page_size = min(100, max_results_per_topic - offset)
                params = {"search_query": build_query(topic, start, end), "start": offset,
                          "max_results": page_size, "sortBy": "submittedDate", "sortOrder": "descending"}
                data = fetch_feed(API_URL + "?" + urllib.parse.urlencode(params))
                papers, total, entries_count = parse_feed(data, start, end, paper_factory)
                candidates.extend(papers)
                offset += entries_count
                if not entries_count or offset >= total:
                    break
            if offset >= max_results_per_topic and offset < total and on_error:
                on_error(topic, f"Candidate limit reached ({offset}/{total}); search was truncated")
        except Exception as exc:
            if on_error:
                on_error(topic, exc)
            else:
                raise
    return candidates
