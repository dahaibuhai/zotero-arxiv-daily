import re


def normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", (title or "").lower()).strip()


def paper_key(paper):
    doi = getattr(paper, "doi", "") or ""
    arxiv_id = getattr(paper, "arxiv_id", "") or ""
    title = normalize_title(getattr(paper, "title", ""))
    if doi:
        return ("doi", doi.lower())
    if arxiv_id:
        return ("id", arxiv_id.lower())
    return ("title", title)


def dedupe_papers(papers):
    seen = set()
    deduped = []
    for paper in papers:
        key = paper_key(paper)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(paper)
    return deduped
